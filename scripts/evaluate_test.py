# ruff: noqa: E501
"""F4.4 / F4b — Los accesos al conjunto de prueba (dos en todo el proyecto).

Único archivo del proyecto autorizado a leer ``test.txt`` (``tests/test_test_split_isolation``).
Orden obligatorio, verificado por ``tests/test_f4_protocol.py``:

0. la bitácora ``logs/test_set_access.log`` tiene menos de dos líneas (si no, se niega: no hay
   tercer acceso) y el número de acceso coincide con el que declara el protocolo;
1. el protocolo (``docs/f4_protocol.yaml`` o, con ``--protocol``, ``docs/f4b_protocol.yaml``)
   está commiteado sin cambios (si no, se niega);
2. el SHA256 de cada checkpoint coincide con el protocolo (si no, se niega);
3. se escribe la bitácora ANTES de leer una sola imagen; el registro es incondicional: si algo
   falla después, el acceso ya quedó registrado;
4. se lee ``test.txt``, se infiere en CPU (uno o varios modelos, con las vistas de TTA del
   protocolo; ensamble = promedio de logits; apilador de metadatos si el protocolo lo trae);
5. se aplican calibración y umbrales tal como están en el protocolo, nada se reajusta;
6. métricas con bootstrap por paciente y subgrupos (F4.5);
7. resultados, predicciones y figuras en las rutas que fija el protocolo (F4: ``configs/f4.yaml``).

Uso: ``uv run python scripts/evaluate_test.py`` (F4, hecho el 2026-09-18) y
``uv run python scripts/evaluate_test.py --protocol docs/f4b_protocol.yaml --reason "F4b …"``
(segundo y último acceso). El protocolo de F4 y sus resultados no se tocan.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from melanoma.data import read_manifest, resolve_paths  # noqa: E402
from melanoma.data.datamodule import (  # noqa: E402
    read_split_ids,
    split_file_sha256,
    verify_split_hashes,
)
from melanoma.eval import (  # noqa: E402
    Platt,
    bootstrap_patient,
    calibration_summary,
    compute_metrics,
    plot_all,
    ppv_npv_at_prevalence,
)
from melanoma.eval.ensemble import apply_frozen_stacker, sigmoid  # noqa: E402
from melanoma.eval.metrics import (  # noqa: E402
    assert_no_accuracy,
    auroc_auprc,
    confusion_at_threshold,
)
from melanoma.eval.predict import (  # noqa: E402
    load_checkpoint,
    predict_views,
    sha256_file,
    split_records,
)
from melanoma.train.run import git_sha  # noqa: E402

TEST_SPLIT = "test"
PROTOCOL = "docs/f4_protocol.yaml"
# Regla del proyecto (README, spec F3b-F4b): el split de prueba se lee como máximo dos veces.
MAX_TEST_ACCESSES = 2
DEFAULT_VIEWS = ["identity"]


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Lee una clave opcional de un protocolo (DictConfig o un objeto simulado en las pruebas)."""
    if hasattr(obj, "get"):
        try:
            value = obj.get(key, default)
        except Exception:  # pragma: no cover - protocolos simulados sin la clave
            return default
        return default if value is None else value
    return getattr(obj, key, default)


# ---- paso 0: presupuesto de accesos -----------------------------------------------------------
def count_access_lines(root: Path, log_path: str) -> int:
    path = root / log_path
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def ensure_access_budget(root: Path, log_path: str, protocol_cfg: Any = None) -> int:
    """Se niega si la bitácora ya tiene ``MAX_TEST_ACCESSES`` líneas: no hay tercer acceso.
    Si el protocolo declara ``access_number``, debe ser exactamente el siguiente."""
    used = count_access_lines(root, log_path)
    if used >= MAX_TEST_ACCESSES:
        raise SystemExit(
            f"{log_path} ya tiene {used} líneas: el presupuesto de accesos al conjunto de prueba "
            f"está agotado ({MAX_TEST_ACCESSES} en todo el proyecto). No hay tercer acceso."
        )
    expected = _get(protocol_cfg, "access_number") if protocol_cfg is not None else None
    if expected is not None and int(expected) != used + 1:
        raise SystemExit(
            f"el protocolo declara el acceso número {int(expected)}, pero la bitácora tiene {used} líneas: "
            f"este sería el acceso {used + 1}. Se niega."
        )
    return used


# ---- pasos 1-3: guardarraíles -------------------------------------------------------------
def ensure_protocol_committed(root: Path, protocol: str = PROTOCOL) -> str:
    """El protocolo debe estar versionado y sin cambios locales. Devuelve su SHA256."""
    tracked = subprocess.check_output(
        ["git", "-C", str(root), "ls-files", "--", protocol], text=True
    ).strip()
    if not tracked:
        raise SystemExit(
            f"{protocol} no está en git: el protocolo debe commitearse antes de evaluar"
        )
    dirty = subprocess.check_output(
        ["git", "-C", str(root), "status", "--porcelain", "--", protocol], text=True
    ).strip()
    if dirty:
        raise SystemExit(f"{protocol} tiene cambios sin commitear ({dirty!r}): se niega a evaluar")
    return hashlib.sha256((root / protocol).read_bytes()).hexdigest()


def protocol_models(protocol_cfg: Any) -> list[dict[str, Any]]:
    """Los modelos del protocolo: ``models`` (F4b, varios) o ``model`` (F4, uno)."""
    models = _get(protocol_cfg, "models")
    if models:
        return [
            {
                "run": str(_get(m, "run", "")),
                "file": str(m.checkpoint_file if _get(m, "checkpoint_file") else m.file),
                "sha256": str(_get(m, "checkpoint_sha256") or m.sha256),
                "backbone": str(m.backbone),
                "image_size": int(m.image_size),
                "val_resize": str(m.val_resize),
                "dropout": _get(m, "dropout"),
                "num_classes": _get(m, "num_classes"),
            }
            for m in models
        ]
    m = protocol_cfg.model
    return [
        {
            "run": str(_get(m, "experiment", "")),
            "file": str(m.checkpoint_file),
            "sha256": str(m.checkpoint_sha256),
            "backbone": str(m.backbone),
            "image_size": int(m.image_size),
            "val_resize": str(m.val_resize),
            "dropout": _get(m, "dropout"),
            "num_classes": _get(m, "num_classes"),
        }
    ]


def protocol_views(protocol_cfg: Any) -> list[str]:
    views = _get(protocol_cfg, "tta")
    return [str(v) for v in views] if views else list(DEFAULT_VIEWS)


def verify_checkpoint(root: Path, protocol_cfg: Any) -> list[str]:
    """Cada checkpoint del protocolo existe y su SHA256 coincide. Devuelve los SHA256."""
    shas = []
    for m in protocol_models(protocol_cfg):
        ckpt = root / "data" / "models" / m["file"]
        if not ckpt.exists():
            raise SystemExit(f"falta el checkpoint {ckpt}")
        sha = sha256_file(ckpt)
        if sha != m["sha256"]:
            raise SystemExit(f"SHA256 del checkpoint {ckpt.name} {sha} ≠ protocolo {m['sha256']}")
        shas.append(sha)
    return shas


def append_access_log(root: Path, log_path: str, protocol_sha: str, reason: str) -> str:
    """Registra el acceso ANTES de leer el split. Incondicional."""
    line = (
        f"{datetime.now(UTC).isoformat(timespec='seconds')}\tgit={git_sha(root)}\t"
        f"protocol_sha256={protocol_sha}\tsplit={TEST_SPLIT}\treason={reason}\n"
    )
    path = root / log_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
    return line


def read_test_ids(splits_dir: Path) -> list[str]:
    """Paso 4: la única lectura de test.txt del proyecto."""
    return read_split_ids(splits_dir, TEST_SPLIT)


# ---- paso 4: inferencia -----------------------------------------------------------------------
def predict_protocol(
    cfg, protocol_cfg: Any, root: Path, recs: pd.DataFrame, images_dir: Path
) -> pd.DataFrame:
    """Logits del protocolo: por modelo y vista, promedio de **logits** (``ensemble: logit_mean``)
    y, si el protocolo trae un apilador congelado, su salida. ``logit`` es la entrada de Platt."""
    views = protocol_views(protocol_cfg)
    per_model = []
    for m in protocol_models(protocol_cfg):
        lit, data_config = load_checkpoint(
            root / "data" / "models" / m["file"],
            m["backbone"],
            int(m["num_classes"] if m["num_classes"] is not None else cfg.model.num_classes),
            float(m["dropout"] if m["dropout"] is not None else cfg.model.dropout),
        )
        z = predict_views(
            lit,
            data_config,
            recs,
            images_dir,
            m["image_size"],
            m["val_resize"],
            views,
            batch_size=cfg.data.batch_size,
            num_workers=cfg.data.num_workers,
        )
        per_model.append(z)
        print(f"  {m['run'] or m['file']}: {z.shape[1]} imágenes × {len(views)} vistas")
    stack = np.stack(per_model)  # (modelos, vistas, imágenes)
    preds = recs.reset_index(drop=True).copy()
    preds["logit_ensemble"] = stack.reshape(-1, stack.shape[-1]).mean(axis=0)
    stacker = _get(protocol_cfg, "stacker")
    if stacker and bool(_get(stacker, "enabled", False)):
        preds["logit"] = apply_frozen_stacker(
            OmegaConf.to_container(stacker, resolve=True)
            if OmegaConf.is_config(stacker)
            else stacker,
            preds,
            preds["logit_ensemble"].to_numpy(),
        )
    else:
        preds["logit"] = preds["logit_ensemble"]
    preds["prob_raw"] = sigmoid(preds["logit"].to_numpy())
    return preds


# ---- pasos 5-7 -----------------------------------------------------------------------------
def age_group(age) -> str:
    if age is None or (isinstance(age, float) and np.isnan(age)):
        return "unknown"
    return "<40" if age < 40 else "40-59" if age < 60 else "60+"


def subgroup_table(
    frame: pd.DataFrame, prob_col: str, tau: float, n_boot: int, seed: int
) -> list[dict]:
    rows = []
    groups = {
        "age": frame["age_approx"].map(age_group),
        "sex": frame["sex"].fillna("unknown").astype(str),
        "site": frame["anatom_site"].fillna("unknown").astype(str),
    }
    for dim, series in groups.items():
        for value in sorted(series.unique(), key=str):
            sub = frame[series == value]
            y = sub["target"].to_numpy()
            p = sub[prob_col].to_numpy()
            row = {
                "dimension": dim,
                "group": str(value),
                "n": int(len(sub)),
                "positives": int(y.sum()),
            }
            if 0 < y.sum() < len(sub):
                auroc, auprc = auroc_auprc(p, y)
                ci = bootstrap_patient(p, y, sub["patient_id"].to_numpy(), n_boot, seed)
                row.update(
                    {
                        "auroc": auroc,
                        "auroc_lo": ci["auroc"]["lo"],
                        "auroc_hi": ci["auroc"]["hi"],
                        "auprc": auprc,
                    }
                )
            else:
                row.update(
                    {
                        "auroc": float("nan"),
                        "auroc_lo": float("nan"),
                        "auroc_hi": float("nan"),
                        "auprc": float("nan"),
                    }
                )
            c = confusion_at_threshold(p, y, tau)
            row.update(
                {"sensitivity_at_tau95": c["sensitivity"], "specificity_at_tau95": c["specificity"]}
            )
            rows.append(row)
    return rows


def evaluate(cfg, protocol_cfg, preds: pd.DataFrame) -> dict:
    """Paso 5-6: calibración y umbrales del protocolo, métricas con IC por paciente."""
    platt = Platt(a=float(protocol_cfg.calibration.a), b=float(protocol_cfg.calibration.b))
    preds = preds.copy()
    preds["prob"] = platt.apply(preds["logit"].to_numpy())
    y, pid, p = preds["target"].to_numpy(), preds["patient_id"].to_numpy(), preds["prob"].to_numpy()
    n_boot, seed = int(protocol_cfg.bootstrap.n), int(protocol_cfg.bootstrap.seed)
    tau95, tau90 = float(protocol_cfg.thresholds.tau_95), float(protocol_cfg.thresholds.tau_90)
    metrics = compute_metrics(p, y, pid, fixed_levels=[0.90, 0.95], threshold=tau95)
    ci = bootstrap_patient(p, y, pid, n_boot, seed)
    conf95, conf90 = confusion_at_threshold(p, y, tau95), confusion_at_threshold(p, y, tau90)
    projections = [
        ppv_npv_at_prevalence(conf95["sensitivity"], conf95["specificity"], prev)
        for prev in protocol_cfg.ppv_npv_projection_prevalences
    ]
    out = {
        "metrics": {k: v for k, v in metrics.items() if k != "curves"},
        "curves": metrics["curves"],
        "ci": ci,
        "calibration": calibration_summary(p, y),
        "calibration_raw": calibration_summary(preds["prob_raw"].to_numpy(), y),
        "confusion_tau_95": conf95,
        "confusion_tau_90": conf90,
        "ppv_npv_projection_tau_95": projections,
        "subgroups": subgroup_table(preds, "prob", tau95, n_boot, seed),
    }
    assert_no_accuracy(out["metrics"])
    return out, preds


def output_paths(cfg, protocol_cfg: Any) -> tuple[str, str, str]:
    """Rutas de salida: las del protocolo (F4b) o las de ``configs/f4.yaml`` (F4)."""
    outputs = _get(protocol_cfg, "outputs")
    if outputs:
        return str(outputs.results_json), str(outputs.predictions_csv), str(outputs.figures_prefix)
    return str(cfg.f4.test_results_json), str(cfg.f4.test_predictions), "f4_test"


def run(cfg, root: Path, reason: str, protocol: str = PROTOCOL) -> dict:
    t0 = time.perf_counter()
    protocol_cfg = OmegaConf.load(root / protocol)
    used = ensure_access_budget(root, cfg.f4.access_log, protocol_cfg)  # 0
    protocol_sha = ensure_protocol_committed(root, protocol)  # 1
    ckpt_shas = verify_checkpoint(root, protocol_cfg)  # 2
    log_line = append_access_log(root, cfg.f4.access_log, protocol_sha, reason)  # 3
    print(f"acceso {used + 1} de {MAX_TEST_ACCESSES} registrado:", log_line.strip())
    paths = resolve_paths(cfg.data, root=root)
    verify_split_hashes(paths.splits_dir)
    ids = read_test_ids(paths.splits_dir)  # 4
    test_sha = split_file_sha256(paths.splits_dir, TEST_SPLIT)
    manifest = read_manifest(paths.manifest_path)
    recs = split_records(manifest, ids)
    preds = predict_protocol(cfg, protocol_cfg, root, recs, paths.images_dir)
    result, preds = evaluate(cfg, protocol_cfg, preds)  # 5-6
    results_json, predictions_csv, figures_prefix = output_paths(cfg, protocol_cfg)
    result.update(
        {
            "date": datetime.now(UTC).isoformat(timespec="seconds"),
            "git_sha": git_sha(root),
            "protocol": protocol,
            "protocol_sha256": protocol_sha,
            "access_number": used + 1,
            "models": protocol_models(protocol_cfg),
            "tta": protocol_views(protocol_cfg),
            "checkpoint_sha256": ckpt_shas[0] if len(ckpt_shas) == 1 else ckpt_shas,
            "test_split_sha256": test_sha,
            "access_log_line": log_line.strip(),
            "n_images": int(len(preds)),
            "n_positives": int(preds["target"].sum()),
            "n_patients": int(preds["patient_id"].nunique()),
            "elapsed_min": (time.perf_counter() - t0) / 60,
        }
    )
    out = root / results_json  # 7
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, default=float), encoding="utf-8")
    pred_path = root / predictions_csv
    pred_path.parent.mkdir(parents=True, exist_ok=True)
    preds.to_csv(pred_path, index=False)
    plot_all(
        {**result["metrics"], "curves": result["curves"]}, root / cfg.f4.figures_dir, figures_prefix
    )
    m, c = result["metrics"], result["ci"]
    print(
        f"TEST: AUROC {m['auroc']:.3f} [{c['auroc']['lo']:.3f}, {c['auroc']['hi']:.3f}]  AUPRC {m['auprc']:.3f} [{c['auprc']['lo']:.3f}, {c['auprc']['hi']:.3f}]"
    )
    print(
        f"τ95: sens {result['confusion_tau_95']['sensitivity']:.3f} spec {result['confusion_tau_95']['specificity']:.3f}  → {out.relative_to(root)}"
    )
    return result


def main() -> None:
    ap = argparse.ArgumentParser(
        description="F4.4 / F4b: acceso al conjunto de prueba (máximo dos)"
    )
    ap.add_argument(
        "--protocol",
        default=PROTOCOL,
        help="docs/f4_protocol.yaml (F4) o docs/f4b_protocol.yaml (F4b)",
    )
    ap.add_argument("--reason", default="F4.4 evaluación clínica (primer acceso)")
    args = ap.parse_args()
    with __import__("hydra").initialize_config_dir(
        config_dir=str(ROOT / "configs"), version_base="1.3"
    ):
        cfg = __import__("hydra").compose(config_name="f4")
    run(cfg, ROOT, args.reason, args.protocol)


if __name__ == "__main__":
    main()
