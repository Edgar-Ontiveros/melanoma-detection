"""CAM en numpy puro para la API: el contrato de F5 (`melanoma.explain.cam`), copiado aquí
porque services/api no puede importar el paquete `melanoma` (arrastraría hydra y omegaconf;
lo vigila tests/test_api_dependency_isolation.py). `tests/test_bundle.py` comprueba que las
dos implementaciones dan lo mismo.

    raw_cam(features[C, H, W], w[C]) → [H, W] sin recortar ni normalizar (Σ_k w_k A_k).
    finalize_cam(raw[H, W]) → ReLU y división por el máximo; todo cero si no hay evidencia
    positiva (no se normaliza un mapa nulo).
    cam_from_features(features, w) = finalize_cam(raw_cam(features, w)).
    ensemble_cam([features_i], [w_i]) = finalize_cam(media_i raw_cam_i): el CAM del ensamble
    (F6b.3) promedia los mapas crudos ANTES de recortar y normalizar; por linealidad es el CAM
    del logit promedio.
    upsample(cam[H, W], size) → [size, size], bilineal con centros desplazados medio píxel.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def raw_cam(features: np.ndarray, linear_weight: np.ndarray) -> np.ndarray:
    a = np.asarray(features, dtype=np.float32)
    w = np.asarray(linear_weight, dtype=np.float32).reshape(-1)
    if a.ndim != 3 or a.shape[0] != w.shape[0]:
        raise ValueError(f"features {a.shape} incompatibles con {w.shape[0]} pesos")
    return np.einsum("chw,c->hw", a, w)


def finalize_cam(raw: np.ndarray) -> np.ndarray:
    cam = np.maximum(np.asarray(raw, dtype=np.float32), 0.0)
    peak = float(cam.max())
    return (cam / peak if peak > 0 else cam).astype(np.float32)


def cam_from_features(features: np.ndarray, linear_weight: np.ndarray) -> np.ndarray:
    return finalize_cam(raw_cam(features, linear_weight))


def ensemble_cam(
    features: Sequence[np.ndarray], linear_weights: Sequence[np.ndarray]
) -> np.ndarray:
    if len(features) != len(linear_weights) or not features:
        raise ValueError("se necesita un mapa de features y un vector de pesos por miembro")
    raws = [raw_cam(f, w) for f, w in zip(features, linear_weights, strict=True)]
    return finalize_cam(np.mean(np.stack(raws), axis=0))


def _axis(n_in: int, n_out: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    src = np.clip((np.arange(n_out, dtype=np.float64) + 0.5) * (n_in / n_out) - 0.5, 0, n_in - 1)
    i0 = np.floor(src).astype(np.int64)
    i1 = np.minimum(i0 + 1, n_in - 1)
    return i0, i1, (src - i0).astype(np.float32)


def upsample(cam: np.ndarray, size: int) -> np.ndarray:
    c = np.asarray(cam, dtype=np.float32)
    r0, r1, rw = _axis(c.shape[0], size)
    c0, c1, cw = _axis(c.shape[1], size)
    top = c[r0][:, c0] * (1 - cw) + c[r0][:, c1] * cw
    bottom = c[r1][:, c0] * (1 - cw) + c[r1][:, c1] * cw
    return (top * (1 - rw)[:, None] + bottom * rw[:, None]).astype(np.float32)
