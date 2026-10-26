# ruff: noqa: E501
"""F6.2 / F6b.2 — Paridad del paquete exportado con PyTorch, solo sobre validación.

Paquete de un solo modelo (``f6.mode=single``, F6) o ensamble (``f6.mode=ensemble``, F6b).
Sobre 200 imágenes de validación al azar (semilla de F6):

  1. logit ONNX vs torch con el mismo tensor (en el ensamble: media de logits de los miembros
     ONNX vs media de los de torch): máx |Δ| < 1e-4
  2. Platt en numpy (API) vs melanoma.eval.Platt: máx |Δ| < 1e-6
  3. CAM de la API (ensamble: media de mapas crudos, luego ReLU y máximo) vs el mismo cálculo
     con features de torch: correlación > 0.999 (los mapas nulos en ambos cuentan como iguales)
  4. decisión en τ95 idéntica en las 200
  5. cadena completa de la API (bytes JPEG de 512 px → PIL → cv2 → ONNX → Platt) vs cadena de
     entrenamiento (albumentations → torch): máx |Δ logit| < 1e-3 y decisiones idénticas
  6. lo mismo desde 100 ORIGINALES de data/raw (hasta 6,000 px) de validación.
  7. (solo ensamble) por miembro, el logit de la cadena completa de la API con las imágenes de
     512 px contra ``reports/predictions/f3b_val_logits.npz`` (vista identity): máx |Δ| ≤ 1e-3.

Uso: uv run python scripts/verify_bundle.py  → reports/f6b_parity.json (o f6_parity.json)
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

import hydra
import numpy as np
import torch
from omegaconf import DictConfig, OmegaConf
from services.api.bundle import load_bundle
from services.api.cam import ensemble_cam as api_ensemble_cam
from services.api.inference import Predictor

from melanoma.data import read_manifest, resolve_paths
from melanoma.data.datamodule import VAL_SPLIT, read_split_ids, verify_split_hashes
from melanoma.data.dataset import ImageDataset
from melanoma.data.resize import resize_one
from melanoma.data.transforms import build_transforms
from melanoma.eval import Platt
from melanoma.eval.predict import load_checkpoint, sha256_file, split_records
from melanoma.explain.features import extract_features
from melanoma.train.run import git_sha

ROOT = Path(__file__).resolve().parents[1]


def load_members(cfg: DictConfig, bundle) -> list[tuple[str, object, dict]]:
    """``[(run, LitBinaryClassifier, data_config)]`` en el orden del paquete, verificando SHA256."""
    out = []
    if bundle.ensemble:
        protocol = OmegaConf.load(ROOT / cfg.f6.ensemble.protocol)
        by_run = {str(m.run): m for m in protocol.models}
        for member in bundle.members:
            m = by_run[member.run]
            ckpt = ROOT / "data" / "models" / str(m.file)
            if sha256_file(ckpt) != member.checkpoint_sha256:
                raise SystemExit(f"{member.run}: el checkpoint local no es el del paquete")
            lit, dc = load_checkpoint(ckpt, str(m.backbone), int(m.num_classes), float(m.dropout))
            out.append((member.run, lit, dc))
    else:
        ckpt = ROOT / cfg.f6.checkpoint
        if bundle.manifest["checkpoint"]["sha256"] != sha256_file(ckpt):
            raise SystemExit("el paquete no corresponde al checkpoint local")
        lit, dc = load_checkpoint(
            ckpt, cfg.model.backbone, cfg.model.num_classes, cfg.model.dropout
        )
        out.append(("model", lit, dc))
    return out


def torch_forward(members, xb: torch.Tensor) -> tuple[float, list[float], np.ndarray]:
    """Media de logits de torch, logits por miembro y CAM del ensamble calculado con features de
    torch (media de mapas crudos w_i·A_i, luego ReLU y máximo)."""
    feats, logits = [], []
    for _, lit, _ in members:
        f, z = extract_features(lit, xb)
        feats.append(np.asarray(f[0]))
        logits.append(float(z[0]))
    weights = [lit.model.head.fc.weight.detach().cpu().numpy().reshape(-1) for _, lit, _ in members]
    return float(np.mean(logits)), logits, api_ensemble_cam(feats, weights)


@hydra.main(config_path="../configs", config_name="f6", version_base="1.3")
def main(cfg: DictConfig) -> None:
    t0 = time.perf_counter()
    is_ensemble = str(cfg.f6.mode) != "single"
    bundle_dir = ROOT / (
        cfg.f6.ensemble.bundle_dir if is_ensemble else cfg.f6.ensemble.single_bundle_dir
    )
    bundle = load_bundle(bundle_dir)
    if bool(bundle.ensemble) != is_ensemble:
        raise SystemExit(f"{bundle_dir} no es un paquete de modo {cfg.f6.mode}")
    members = load_members(cfg, bundle)
    data_config = members[0][2]
    paths = resolve_paths(cfg.data, root=ROOT)
    hashes = verify_split_hashes(paths.splits_dir)
    recs = split_records(
        read_manifest(paths.manifest_path), read_split_ids(paths.splits_dir, VAL_SPLIT)
    )
    rng = np.random.default_rng(int(cfg.f6.seed))
    idx = np.sort(rng.choice(len(recs), size=int(cfg.f6.n_parity), replace=False))
    sample = recs.iloc[idx].reset_index(drop=True)
    image_size = int(bundle.preprocess["input_size"])
    transform = build_transforms(
        data_config, image_size, None, train=False, val_resize=str(bundle.preprocess["val_resize"])
    )
    ds = ImageDataset(sample, paths.images_dir, transform)
    predictor = Predictor(bundle, int(cfg.f6.intra_op_threads))
    platt = Platt(a=float(bundle.calibration["a"]), b=float(bundle.calibration["b"]))
    tau = predictor.threshold
    tol = cfg.f6.tolerances

    d_logit, d_platt, cam_corr, cam_both_zero = [], [], [], 0
    dec_torch, dec_onnx, d_chain, dec_chain = [], [], [], []
    chain_member_logits: list[list[float]] = []
    for i in range(len(ds)):
        x, _ = ds[i]
        xb = x[None]
        logit_t, _, cam_t = torch_forward(members, xb)
        # 1–4: mismo tensor
        onnx_logits, onnx_feats = [], []
        for session in predictor.sessions:
            lo, fe = session.run(predictor.output_names, {predictor.input_name: xb.numpy()})
            onnx_logits.append(float(lo[0, 0]))
            onnx_feats.append(fe[0])
        logit_o = float(np.mean(onnx_logits))
        d_logit.append(abs(logit_o - logit_t))
        p_ref = float(platt.apply(np.array([logit_o]))[0])
        p_api = predictor.calibrate(logit_o)
        d_platt.append(abs(p_api - p_ref))
        cam_a = api_ensemble_cam(onnx_feats, predictor.cam_weights)
        if cam_t.max() == 0 and cam_a.max() == 0:
            cam_both_zero += 1
        else:
            cam_corr.append(float(np.corrcoef(cam_t.ravel(), cam_a.ravel())[0, 1]))
        dec_torch.append(bool(platt.apply(np.array([logit_t]))[0] >= tau))
        dec_onnx.append(bool(p_api >= tau))
        # 5: cadena completa desde los bytes del JPEG
        data = (paths.images_dir / f"{sample['image_id'][i]}.jpg").read_bytes()
        pred = predictor.predict_bytes(data)
        d_chain.append(abs(pred.logit - logit_t))
        dec_chain.append(pred.refer)
        chain_member_logits.append(pred.member_logits)

    # 6: originales de data/raw → API (dos etapas) vs resize_one de F1 + cadena de entrenamiento
    raw_dir = ROOT / cfg.f6.raw_images_dir
    n_orig = int(cfg.f6.n_parity_originals)
    orig_idx = np.sort(rng.choice(len(recs), size=n_orig, replace=False))
    originals = recs.iloc[orig_idx].reset_index(drop=True)
    s1 = bundle.preprocess["stage1"]
    d_orig, dec_orig_ref, dec_orig_api, orig_sides, orig_bytes = [], [], [], [], []
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(len(originals)):
            iid = str(originals["image_id"][i])
            src = raw_dir / f"{iid}.jpg"
            dst = Path(tmp) / f"{iid}.jpg"
            resize_one(src, dst, int(s1["long_side"]), int(s1["jpeg_quality"]))
            ref_ds = ImageDataset(originals.iloc[[i]].reset_index(drop=True), tmp, transform)
            logit_ref, _, _ = torch_forward(members, ref_ds[0][0][None])
            data = src.read_bytes()
            pred = predictor.predict_bytes(data)
            d_orig.append(abs(pred.logit - logit_ref))
            dec_orig_ref.append(bool(platt.apply(np.array([logit_ref]))[0] >= tau))
            dec_orig_api.append(pred.refer)
            orig_sides.append(max(pred.input_info["width"], pred.input_info["height"]))
            orig_bytes.append(len(data))
    d_orig = np.array(d_orig)

    d_logit, d_platt, d_chain = np.array(d_logit), np.array(d_platt), np.array(d_chain)
    corr = np.array(cam_corr)
    result = {
        "date": time.strftime("%Y-%m-%d"),
        "git_sha": git_sha(ROOT),
        "mode": "ensemble" if is_ensemble else "single",
        "model_version": bundle.model_version,
        "members": [m.run for m in bundle.members],
        "checkpoint_sha256": [m.checkpoint_sha256 for m in bundle.members],
        "split_sha256": hashes,
        "n": int(len(ds)),
        "seed": int(cfg.f6.seed),
        "image_ids": sample["image_id"].tolist(),
        "logit": {
            "max_abs_diff": float(d_logit.max()),
            "mean_abs_diff": float(d_logit.mean()),
            "tolerance": float(tol.logit),
            "pass": bool(d_logit.max() < tol.logit),
        },
        "platt": {
            "max_abs_diff": float(d_platt.max()),
            "tolerance": float(tol.platt),
            "pass": bool(d_platt.max() < tol.platt),
        },
        "cam": {
            "n_correlated": int(corr.size),
            "n_both_zero": int(cam_both_zero),
            "min_corr": float(corr.min()) if corr.size else None,
            "mean_corr": float(corr.mean()) if corr.size else None,
            "tolerance": float(tol.cam_corr),
            "pass": bool((corr > tol.cam_corr).all()) if corr.size else True,
        },
        "decision_tau95": {
            "n_differ": int(sum(a != b for a, b in zip(dec_torch, dec_onnx, strict=True))),
            "n_refer": int(sum(dec_onnx)),
            "pass": dec_torch == dec_onnx,
        },
        "full_chain": {
            "max_abs_diff_logit": float(d_chain.max()),
            "mean_abs_diff_logit": float(d_chain.mean()),
            "p95_abs_diff_logit": float(np.quantile(d_chain, 0.95)),
            "tolerance": float(tol.full_chain_logit),
            "pass": bool(d_chain.max() < tol.full_chain_logit),
            "n_decisions_differ": int(
                sum(a != b for a, b in zip(dec_torch, dec_chain, strict=True))
            ),
            "decisions_identical": dec_torch == dec_chain,
        },
        "full_chain_originals": {
            "n": int(len(d_orig)),
            "image_ids": originals["image_id"].tolist(),
            "source": str(cfg.f6.raw_images_dir),
            "long_side_min": int(min(orig_sides)),
            "long_side_max": int(max(orig_sides)),
            "bytes_max": int(max(orig_bytes)),
            "stage1": s1,
            "max_abs_diff_logit": float(d_orig.max()),
            "mean_abs_diff_logit": float(d_orig.mean()),
            "p95_abs_diff_logit": float(np.quantile(d_orig, 0.95)),
            "tolerance": float(tol.full_chain_logit),
            "pass": bool(d_orig.max() < tol.full_chain_logit),
            "n_decisions_differ": int(
                sum(a != b for a, b in zip(dec_orig_ref, dec_orig_api, strict=True))
            ),
            "decisions_identical": dec_orig_ref == dec_orig_api,
        },
    }
    checks = ["logit", "platt", "cam", "decision_tau95", "full_chain", "full_chain_originals"]

    if is_ensemble:  # 7: por miembro contra el caché de logits de F3b (vista identity)
        cache = np.load(ROOT / cfg.f6.ensemble.val_logits_npz, allow_pickle=False)
        members_c, views_c, ids_c = (
            list(cache["members"]),
            list(cache["views"]),
            list(cache["image_id"]),
        )
        pos = {iid: k for k, iid in enumerate(ids_c)}
        rows = np.array([pos[iid] for iid in sample["image_id"]])
        ident = views_c.index("identity")
        per_member, tol_c = {}, float(cfg.f6.ensemble.tolerance_vs_cache)
        api_logits = np.array(chain_member_logits)  # (n, miembros)
        for j, m in enumerate(bundle.members):
            ref = cache["logits"][members_c.index(m.run), ident, rows].astype(np.float64)
            d = np.abs(api_logits[:, j] - ref)
            per_member[m.run] = {
                "max_abs_diff": float(d.max()),
                "mean_abs_diff": float(d.mean()),
                "pass": bool(d.max() <= tol_c),
            }
        result["vs_val_logits_cache"] = {
            "file": str(cfg.f6.ensemble.val_logits_npz),
            "view": "identity",
            "tolerance": tol_c,
            "max_abs_diff": max(v["max_abs_diff"] for v in per_member.values()),
            "per_member": per_member,
            "pass": all(v["pass"] for v in per_member.values()),
        }
        checks.append("vs_val_logits_cache")
    result["minutes"] = (time.perf_counter() - t0) / 60
    result["all_pass"] = all(result[k]["pass"] for k in checks)
    out = ROOT / (cfg.f6.ensemble.parity_json if is_ensemble else cfg.f6.parity_json)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        f"logit máx |Δ| {d_logit.max():.2e} (< {tol.logit}) · Platt máx |Δ| {d_platt.max():.2e} · CAM corr mín {result['cam']['min_corr']} (ambas cero: {cam_both_zero}) · decisiones distintas: {result['decision_tau95']['n_differ']}"
    )
    print(
        f"cadena completa: logit máx |Δ| {d_chain.max():.2e} media {d_chain.mean():.2e} p95 {result['full_chain']['p95_abs_diff_logit']:.2e} (< {tol.full_chain_logit}) · decisiones distintas: {result['full_chain']['n_decisions_differ']}"
    )
    fo = result["full_chain_originals"]
    print(
        f"originales ({fo['n']}, lado largo {fo['long_side_min']}–{fo['long_side_max']}): logit máx |Δ| {fo['max_abs_diff_logit']:.2e} media {fo['mean_abs_diff_logit']:.2e} p95 {fo['p95_abs_diff_logit']:.2e} · decisiones distintas: {fo['n_decisions_differ']}"
    )
    if is_ensemble:
        c = result["vs_val_logits_cache"]
        print(
            f"vs caché F3b (identity): máx |Δ| {c['max_abs_diff']:.2e} (≤ {c['tolerance']}) · "
            + ", ".join(f"{k} {v['max_abs_diff']:.2e}" for k, v in c["per_member"].items())
        )
    print(f"all_pass={result['all_pass']} → {out.relative_to(ROOT)} · {result['minutes']:.1f} min")


if __name__ == "__main__":
    main()
