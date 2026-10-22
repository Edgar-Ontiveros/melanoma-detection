# ruff: noqa: E501
"""F3b.1 y F3b.2 — Verificación de los nueve checkpoints de F3 y caché de logits sobre validación.

F3b.1: por miembro, SHA256 y tamaño del checkpoint, y AUC-ROC de validación recalculado en CPU
contra el que reportó su corrida en Kaggle (`reports/runs/<corrida>/runs/*/metrics.json`); si la
diferencia supera la tolerancia, el miembro queda marcado como excluido y no entra al ensamble.
F3b.2: logits de cada miembro para cada vista de TTA (identidad y volteos) sobre las 4,963
imágenes de validación, en un solo npz alineado con `image_id`, `target` y `patient_id`.

Solo validación: el split de prueba no se toca. Salidas: reports/f3b_checkpoints.json y
reports/predictions/f3b_val_logits.npz. Caché parcial por miembro en outputs/f3b/logits/.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import hydra
import numpy as np
from omegaconf import DictConfig, OmegaConf

from melanoma.data import read_manifest, resolve_paths
from melanoma.data.datamodule import VAL_SPLIT, read_split_ids, verify_split_hashes
from melanoma.eval.ensemble import VIEW_FLIPS
from melanoma.eval.metrics import auroc_auprc
from melanoma.eval.predict import load_checkpoint, predict_views, sha256_file, split_records
from melanoma.train.run import git_sha

ROOT = Path(__file__).resolve().parents[1]


def run_dir_of(runs_dir: Path, member: str) -> Path:
    """La carpeta `runs/<tag>-<sha>/` de la corrida bajada de Kaggle (una por miembro)."""
    candidates = sorted((runs_dir / member / "runs").glob(f"{member}-*"))
    if len(candidates) != 1:
        raise SystemExit(f"{member}: se esperaba una carpeta de corrida, hay {len(candidates)}")
    return candidates[0]


def member_spec(runs_dir: Path, models_dir: Path, member: str) -> dict:
    """Backbone, resolución, geometría y checkpoint esperado, leídos de la corrida misma."""
    rd = run_dir_of(runs_dir, member)
    cfg = OmegaConf.load(rd / "config.yaml")
    metrics = json.loads((rd / "metrics.json").read_text(encoding="utf-8"))
    ckpt_name = Path(str(metrics["best_checkpoint"])).name
    return {
        "run": member,
        "run_dir": str(rd.relative_to(ROOT)),
        "experiment": str(cfg.experiment),
        "backbone": str(cfg.model.backbone),
        "image_size": int(cfg.data.image_size),
        "val_resize": str(cfg.data.val_resize),
        "dropout": float(cfg.model.dropout),
        "num_classes": int(cfg.model.num_classes),
        "file": ckpt_name,
        "path": models_dir / ckpt_name,
        "auroc_run": float(metrics["metrics"]["auroc"]),
        "auprc_run": float(metrics["metrics"]["auprc"]),
    }


@hydra.main(config_path="../configs", config_name="f3b", version_base="1.3")
def main(cfg: DictConfig) -> None:
    t0 = time.perf_counter()
    f = cfg.f3b
    views = [str(v) for v in f.views]
    unknown = [v for v in views if v not in VIEW_FLIPS]
    if unknown:
        raise SystemExit(f"vistas desconocidas: {unknown}; opciones: {sorted(VIEW_FLIPS)}")
    paths = resolve_paths(cfg.data, root=ROOT)
    split_hashes = verify_split_hashes(paths.splits_dir)
    manifest = read_manifest(paths.manifest_path)
    recs = split_records(manifest, read_split_ids(paths.splits_dir, VAL_SPLIT))
    y = recs["target"].to_numpy()
    print(
        f"validación: {len(recs)} imágenes, {int(y.sum())} melanomas, {recs['patient_id'].nunique()} pacientes"
    )

    runs_dir, models_dir = ROOT / f.runs_dir, ROOT / f.models_dir
    partial_dir = ROOT / f.partial_dir
    partial_dir.mkdir(parents=True, exist_ok=True)
    members, logits = [], []
    for member in [str(m) for m in f.members]:
        spec = member_spec(runs_dir, models_dir, member)
        ckpt: Path = spec.pop("path")
        if not ckpt.exists():
            raise SystemExit(
                f"{member}: falta {ckpt.relative_to(ROOT)} (kaggle_run.py checkpoint {member})"
            )
        spec["bytes"] = ckpt.stat().st_size
        spec["sha256"] = sha256_file(ckpt)
        partial = partial_dir / f"{member}.npz"
        t1 = time.perf_counter()
        if f.reuse_partial and partial.exists():
            cached = np.load(partial, allow_pickle=False)
            same = (
                str(cached["sha256"]) == spec["sha256"]
                and list(cached["views"]) == views
                and list(cached["image_id"]) == recs["image_id"].tolist()
            )
            z = cached["logits"] if same else None
        else:
            z = None
        if z is None:
            lit, data_config = load_checkpoint(
                ckpt, spec["backbone"], spec["num_classes"], spec["dropout"]
            )
            z = predict_views(
                lit,
                data_config,
                recs,
                paths.images_dir,
                spec["image_size"],
                spec["val_resize"],
                views,
                batch_size=int(cfg.data.batch_size),
                num_workers=int(cfg.data.num_workers),
            ).astype(np.float32)
            np.savez(
                partial,
                logits=z,
                views=np.array(views),
                image_id=recs["image_id"].to_numpy().astype(str),
                sha256=spec["sha256"],
            )
            spec["inference_min"] = round((time.perf_counter() - t1) / 60, 2)
        else:
            spec["inference_min"] = None
        # F3b.1: la vista identidad debe reproducir el AUC-ROC de la corrida.
        p = 1.0 / (1.0 + np.exp(-z[views.index("identity")].astype(np.float64)))
        auroc, auprc = auroc_auprc(p, y)
        spec["auroc_reproduced"], spec["auprc_reproduced"] = auroc, auprc
        spec["auroc_diff"] = auroc - spec["auroc_run"]
        spec["ok"] = abs(spec["auroc_diff"]) < float(f.auroc_tolerance)
        spec["excluded"] = not spec["ok"]
        flag = "OK" if spec["ok"] else "EXCLUIDO"
        print(
            f"{member:6s} {spec['file']}  sha {spec['sha256'][:12]}…  AUC corrida {spec['auroc_run']:.4f}  local {auroc:.4f}  Δ {spec['auroc_diff']:+.4f}  {flag}"
        )
        members.append(spec)
        logits.append(z)

    result = {
        "date": time.strftime("%Y-%m-%d"),
        "git_sha": git_sha(ROOT),
        "split": VAL_SPLIT,
        "split_sha256": split_hashes.get(VAL_SPLIT) if isinstance(split_hashes, dict) else None,
        "n_images": int(len(recs)),
        "n_positives": int(y.sum()),
        "n_patients": int(recs["patient_id"].nunique()),
        "views": views,
        "auroc_tolerance": float(f.auroc_tolerance),
        "n_ok": int(sum(m["ok"] for m in members)),
        "excluded": [m["run"] for m in members if m["excluded"]],
        "members": members,
    }
    out_json = ROOT / f.checkpoints_json
    out_json.write_text(json.dumps(result, indent=2, default=float), encoding="utf-8")
    out_npz = ROOT / f.logits_npz
    out_npz.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out_npz,
        logits=np.stack(logits),  # (miembros, vistas, imágenes)
        members=np.array([m["run"] for m in members]),
        excluded=np.array([m["excluded"] for m in members]),
        checkpoint_sha256=np.array([m["sha256"] for m in members]),
        views=np.array(views),
        image_id=recs["image_id"].to_numpy().astype(str),
        target=y.astype(np.int64),
        patient_id=recs["patient_id"].to_numpy().astype(str),
    )
    print(
        f"{result['n_ok']}/{len(members)} checkpoints reproducen su AUC; excluidos: {result['excluded'] or 'ninguno'}"
    )
    print(
        f"→ {out_json.relative_to(ROOT)}, {out_npz.relative_to(ROOT)} en {(time.perf_counter() - t0) / 60:.1f} min"
    )


if __name__ == "__main__":
    main()
