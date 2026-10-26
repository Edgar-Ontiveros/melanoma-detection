"""Carga del paquete de modelo (F6.3, F6b). La API no conoce ningún número del modelo: todo
se lee de aquí, y antes de servir se verifica el SHA256 de cada archivo contra el manifiesto.
Un paquete a medias o alterado no levanta. Un paquete puede traer un modelo (F6: ``model.onnx``)
o varios (F6b: ``members`` en el manifiesto, ensamble por promedio de logits)."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

ENV_BUNDLE_DIR = "MODEL_BUNDLE_DIR"
REQUIRED_JSON = ("preprocess.json", "calibration.json", "thresholds.json", "metrics.json")
SINGLE_MODEL_FILES = ("model.onnx", "cam_weights.npy")
REQUIRED_FILES = SINGLE_MODEL_FILES + REQUIRED_JSON  # paquete de un solo modelo (F6)


class BundleError(RuntimeError):
    """El paquete no existe, está incompleto o su SHA256 no coincide."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_manifest(bundle_dir: Path) -> dict[str, Any]:
    """Devuelve el manifiesto si todos los archivos existen y sus SHA256 coinciden."""
    manifest_path = bundle_dir / "manifest.json"
    if not manifest_path.exists():
        raise BundleError(f"falta {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest.get("files", {})
    required = list(REQUIRED_JSON)
    members = manifest.get("members")
    if members:  # ensamble (F6b): un ONNX y unos pesos por miembro
        for m in members:
            required += [str(m["onnx"]), str(m["cam_weights"])]
    else:
        required += list(SINGLE_MODEL_FILES)
    missing = [f for f in required if f not in files]
    if missing:
        raise BundleError(f"el manifiesto no lista {missing}")
    for name, expected in files.items():
        path = bundle_dir / name
        if not path.exists():
            raise BundleError(f"falta {path}")
        actual = sha256_file(path)
        if actual != expected:
            raise BundleError(f"SHA256 de {name} no coincide: {actual[:12]}… ≠ {expected[:12]}…")
    return manifest


@dataclass(frozen=True)
class Member:
    """Un modelo del paquete: su ONNX y los pesos de la cabeza lineal para el CAM."""

    run: str
    onnx_path: Path
    cam_weights: np.ndarray
    checkpoint_sha256: str


@dataclass(frozen=True)
class Bundle:
    dir: Path
    manifest: dict[str, Any]
    preprocess: dict[str, Any]
    calibration: dict[str, Any]
    thresholds: dict[str, Any]
    metrics: dict[str, Any]
    members: tuple[Member, ...]

    @property
    def model_version(self) -> str:
        return str(self.manifest["model_version"])

    @property
    def ensemble(self) -> str | None:
        """Método del ensamble (``logit_mean``) o ``None`` si el paquete es de un solo modelo."""
        e = self.manifest.get("ensemble")
        return str(e["method"]) if e else None

    @property
    def n_members(self) -> int:
        return len(self.members)

    @property
    def onnx_path(self) -> Path:
        """El ONNX del paquete de un solo modelo (F6). Un ensamble tiene ``members``."""
        if self.n_members != 1:
            raise BundleError("el paquete es un ensamble: usar bundle.members")
        return self.members[0].onnx_path

    @property
    def cam_weights(self) -> np.ndarray:
        if self.n_members != 1:
            raise BundleError("el paquete es un ensamble: usar bundle.members")
        return self.members[0].cam_weights

    @property
    def operating(self) -> dict[str, Any]:
        """Umbral de operación (τ95) con su sensibilidad objetivo y las métricas del test."""
        key = self.thresholds["operating"]
        t = self.thresholds[key]
        test = self.metrics.get(key, {})
        return {
            "key": key,
            "threshold": float(t["tau"]),
            "sensitivity_target": float(t["sensitivity_target"]),
            "sensitivity_test": test.get("sensitivity"),
            "specificity_test": test.get("specificity"),
        }


def bundle_dir_from_env() -> Path:
    value = os.environ.get(ENV_BUNDLE_DIR)
    if not value:
        raise BundleError(f"define {ENV_BUNDLE_DIR} con la ruta del paquete de modelo")
    return Path(value)


def load_bundle(bundle_dir: Path | None = None) -> Bundle:
    d = bundle_dir if bundle_dir is not None else bundle_dir_from_env()
    if not d.is_dir():
        raise BundleError(f"{d} no es un directorio")
    manifest = verify_manifest(d)

    def read(name: str) -> dict[str, Any]:
        return json.loads((d / name).read_text(encoding="utf-8"))

    def weights(name: str) -> np.ndarray:
        return np.load(d / name).astype(np.float32).reshape(-1)

    if manifest.get("members"):
        members = tuple(
            Member(
                run=str(m["run"]),
                onnx_path=d / str(m["onnx"]),
                cam_weights=weights(str(m["cam_weights"])),
                checkpoint_sha256=str(m["checkpoint"]["sha256"]),
            )
            for m in manifest["members"]
        )
    else:
        members = (
            Member(
                run="model",
                onnx_path=d / "model.onnx",
                cam_weights=weights("cam_weights.npy"),
                checkpoint_sha256=str(manifest["checkpoint"]["sha256"]),
            ),
        )
    return Bundle(
        dir=d,
        manifest=manifest,
        preprocess=read("preprocess.json"),
        calibration=read("calibration.json"),
        thresholds=read("thresholds.json"),
        metrics=read("metrics.json"),
        members=members,
    )
