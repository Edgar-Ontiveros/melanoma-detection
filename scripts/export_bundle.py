# ruff: noqa: E501
"""F6.1 / F6b.1 — Exporta el paquete de modelo a models/.

``f6.mode=ensemble`` (por defecto, F6b): los tres checkpoints de `docs/f4b_protocol.yaml`,
un ONNX y unos pesos de cabeza por miembro, calibración y umbrales copiados del protocolo y
comparados valor por valor (se detiene si algo difiere), métricas del test de F4b con IC en τ95
y un bloque ``previous_model`` con las del modelo único de F4. Nombre ``model-<git>-<sha8>``
con sha8 = SHA256 de los SHA256 de los miembros.

``f6.mode=single``: el paquete de F6 (un checkpoint) a ``single_bundle_dir``.

Uso: uv run python scripts/export_bundle.py [f6.mode=single]
"""

from __future__ import annotations

import json
from pathlib import Path

import hydra
import numpy as np
import pandas as pd
from omegaconf import DictConfig, OmegaConf

from melanoma.eval import bootstrap_patient
from melanoma.eval.metrics import confusion_at_threshold
from melanoma.eval.predict import load_checkpoint, sha256_file
from melanoma.export.bundle import (
    calibration_spec,
    metrics_spec,
    protocol_mismatches,
    stage1_spec,
    thresholds_spec,
    write_bundle,
    write_ensemble_bundle,
)
from melanoma.train.run import git_sha

ROOT = Path(__file__).resolve().parents[1]


def tau95_ci(predictions_csv: Path, tau: float, n_boot: int, seed: int) -> dict:
    """IC por bootstrap a nivel paciente de sensibilidad, especificidad, VPP y VPN en τ95, a
    partir de las predicciones ya guardadas del test (no se vuelve a leer el split)."""
    df = pd.read_csv(predictions_csv)
    p, y, pid = df["prob"].to_numpy(), df["target"].to_numpy(), df["patient_id"].to_numpy()
    fns = {
        k: (lambda pp, yy, _k=k: float(confusion_at_threshold(pp, yy, tau)[_k]))
        for k in ("sensitivity", "specificity", "ppv", "npv")
    }
    ci = bootstrap_patient(p, y, pid, n_boot, seed, metric_fns=fns)
    return {k: {kk: float(v[kk]) for kk in ("point", "lo", "hi")} for k, v in ci.items()}


def export_single(cfg: DictConfig) -> None:
    ckpt = ROOT / cfg.f6.checkpoint
    sha = sha256_file(ckpt)
    expected = json.loads((ROOT / cfg.f6.checkpoint_manifest).read_text())["sha256"]
    if sha != expected:
        raise SystemExit(f"SHA256 del checkpoint {sha} ≠ {expected} ({cfg.f6.checkpoint_manifest})")
    lit, data_config = load_checkpoint(
        ckpt, cfg.model.backbone, cfg.model.num_classes, cfg.model.dropout
    )
    f4 = json.loads((ROOT / cfg.f6.calibration_json).read_text())
    f4_test = json.loads((ROOT / cfg.f6.test_results_json).read_text())
    if f4["checkpoint"]["sha256"] != sha or f4_test["checkpoint_sha256"] != sha:
        raise SystemExit("la calibración o las métricas de F4 no corresponden a este checkpoint")
    out = ROOT / cfg.f6.ensemble.single_bundle_dir
    manifest = write_bundle(
        lit.model,
        data_config,
        out,
        image_size=int(cfg.data.image_size),
        val_resize=str(cfg.data.val_resize),
        stage1=stage1_spec(int(cfg.data.resize.long_side), int(cfg.data.resize.jpeg_quality)),
        opset=int(cfg.f6.opset),
        calibration=calibration_spec(f4),
        thresholds=thresholds_spec(f4),
        metrics=metrics_spec(f4_test),
        checkpoint_sha256=sha,
        checkpoint_file=ckpt.name,
        git_sha=git_sha(ROOT),
        extra={"kind": "release", "backbone": str(cfg.model.backbone)},
    )
    print(json.dumps({k: manifest[k] for k in ("model_version", "onnx", "files")}, indent=2))
    print(
        f"→ {out.relative_to(ROOT)} ({sum((out / f).stat().st_size for f in manifest['files']) / 1e6:.1f} MB)"
    )


def export_ensemble(cfg: DictConfig) -> None:
    e = cfg.f6.ensemble
    protocol = OmegaConf.to_container(OmegaConf.load(ROOT / e.protocol), resolve=True)
    f3b = json.loads((ROOT / e.ensemble_json).read_text())
    f4b_test = json.loads((ROOT / e.test_results_json).read_text())
    f4_test = json.loads((ROOT / e.previous_test_results_json).read_text())
    n_boot, seed = int(protocol["bootstrap"]["n"]), int(protocol["bootstrap"]["seed"])

    members, data_config = [], None
    for m in protocol["models"]:
        ckpt = ROOT / "data" / "models" / str(m["file"])
        sha = sha256_file(ckpt)
        if sha != str(m["sha256"]):
            raise SystemExit(f"{m['run']}: SHA256 {sha} ≠ protocolo {m['sha256']}")
        lit, data_config = load_checkpoint(
            ckpt, str(m["backbone"]), int(m["num_classes"]), float(m["dropout"])
        )
        members.append(
            {
                "run": str(m["run"]),
                "model": lit.model,
                "checkpoint_file": ckpt.name,
                "checkpoint_sha256": sha,
            }
        )
        print(f"  {m['run']}: {ckpt.name} sha {sha[:12]}… OK")
    sizes = {int(m["image_size"]) for m in protocol["models"]}
    resizes = {str(m["val_resize"]) for m in protocol["models"]}
    if len(sizes) != 1 or len(resizes) != 1:
        raise SystemExit(
            "los miembros deben compartir resolución y geometría (un solo preprocesamiento)"
        )
    image_size, val_resize = sizes.pop(), resizes.pop()

    final = f3b["final"]
    calibration = {
        "method": "platt",
        "a": float(protocol["calibration"]["a"]),
        "b": float(protocol["calibration"]["b"]),
        "fitted_on": "validation",
        "input": str(protocol["calibration"].get("input", "ensemble_logit")),
        "n_images": int(f3b["n_images"]),
        "n_positives": int(f3b["n_positives"]),
        "date": str(protocol["frozen_on"]),
        "source": str(e.protocol),
    }
    thresholds = {"operating": "tau_95", "source": str(e.protocol)}
    for key in ("tau_95", "tau_90"):
        t = final["thresholds"][key]
        o = protocol["thresholds"]["on_val"][key]
        if abs(float(t["tau"]) - float(protocol["thresholds"][key])) > 1e-12:
            raise SystemExit(f"{key} de reports/f3b_ensemble.json ≠ protocolo")
        thresholds[key] = {
            "tau": float(protocol["thresholds"][key]),
            "sensitivity_target": float(t["sensitivity_target"]),
            "p05": float(t["p05"]),
            "p95": float(t["p95"]),
            "validation": {k: float(o[k]) for k in ("sensitivity", "specificity", "ppv", "npv")},
        }
    metrics = metrics_spec(f4b_test)
    metrics.update(
        {
            "accessed_once": False,
            "access_number": 2,
            "label": "ensamble E1 (F4b)",
            "source": str(e.test_results_json),
        }
    )
    metrics["tau_95"]["ci"] = tau95_ci(
        ROOT / e.test_predictions, metrics["tau_95"]["threshold"], n_boot, seed
    )
    previous = metrics_spec(f4_test)
    previous.update(
        {
            "label": "modelo único (F4)",
            "access_number": 1,
            "source": str(e.previous_test_results_json),
        }
    )
    previous["tau_95"]["ci"] = tau95_ci(
        ROOT / e.previous_test_predictions, previous["tau_95"]["threshold"], n_boot, seed
    )
    metrics["previous_model"] = previous
    metrics["base_rate"] = {
        "prevalence": float(f4b_test["metrics"]["prevalence"]),
        "source": "prevalencia observada en el conjunto de prueba (F4b)",
    }

    out = ROOT / e.bundle_dir
    manifest = write_ensemble_bundle(
        members,
        data_config,
        out,
        image_size=image_size,
        val_resize=val_resize,
        stage1=stage1_spec(int(cfg.data.resize.long_side), int(cfg.data.resize.jpeg_quality)),
        opset=int(cfg.f6.opset),
        calibration=calibration,
        thresholds=thresholds,
        metrics=metrics,
        git_sha=git_sha(ROOT),
        extra={
            "kind": "release",
            "backbone": str(protocol["models"][0]["backbone"]),
            "protocol": {
                "file": str(e.protocol),
                "winner": str(protocol["winner"]["name"]),
                "frozen_on": str(protocol["frozen_on"]),
            },
        },
    )
    mismatches = protocol_mismatches(manifest, calibration, thresholds, protocol)
    if mismatches:
        raise SystemExit("el paquete no coincide con el protocolo:\n- " + "\n- ".join(mismatches))
    size = sum((out / f).stat().st_size for f in manifest["files"]) / 1e6
    print(json.dumps({k: manifest[k] for k in ("model_version", "ensemble", "onnx")}, indent=2))
    print(
        f"miembros: {[m['run'] for m in manifest['members']]} · protocolo verificado valor por valor"
    )
    print(f"→ {out.relative_to(ROOT)} ({size:.1f} MB)")


@hydra.main(config_path="../configs", config_name="f6", version_base="1.3")
def main(cfg: DictConfig) -> None:
    np.random.seed(0)
    if str(cfg.f6.mode) == "single":
        export_single(cfg)
    else:
        export_ensemble(cfg)


if __name__ == "__main__":
    main()
