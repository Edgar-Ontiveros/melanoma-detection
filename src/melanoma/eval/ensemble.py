"""Ensamble, TTA, regla de decisión y apilador de metadatos (F3b).

Todo opera sobre logits en caché (``reports/predictions/f3b_val_logits.npz``) o sobre los
logits que produce la inferencia de F4b. Sin constantes de configuración: candidatos, costos y
umbrales llegan desde ``configs/f3b.yaml`` o desde ``docs/f4b_protocol.yaml``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd
import torch
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegressionCV
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# ---- vistas de TTA ----------------------------------------------------------------------------
# Volteos sobre el tensor CHW ya normalizado: exactos (sin reinterpolar), nombrados e involutivos.
VIEW_FLIPS: dict[str, tuple[int, ...]] = {
    "identity": (),
    "hflip": (-1,),
    "vflip": (-2,),
    "hvflip": (-2, -1),
}


def apply_view(x: torch.Tensor, view: str) -> torch.Tensor:
    if view not in VIEW_FLIPS:
        raise ValueError(f"vista desconocida: {view!r}; opciones: {sorted(VIEW_FLIPS)}")
    dims = VIEW_FLIPS[view]
    return torch.flip(x, dims=dims) if dims else x


# ---- ensamble ---------------------------------------------------------------------------------
def mean_logits(logits: np.ndarray, members: Sequence[int], views: Sequence[int]) -> np.ndarray:
    """Promedio de **logits** (no de probabilidades) sobre ``members`` × ``views``.

    ``logits`` tiene forma ``(miembros, vistas, imágenes)``. El promedio de logits conmuta con
    Platt (``a·mean(z) + b``) y es lo estándar para ensamblar clasificadores binarios.
    """
    z = np.asarray(logits, dtype=np.float64)
    if z.ndim != 3:
        raise ValueError(f"se esperaba (miembros, vistas, imágenes), llegó {z.shape}")
    sub = z[np.ix_(list(members), list(views))]
    return sub.reshape(-1, z.shape[-1]).mean(axis=0)


def sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.asarray(z, dtype=np.float64)))


# ---- regla de decisión de F3b.3 ---------------------------------------------------------------
def latency_ms(cost_gflops: float, ms_per_gflop: float) -> float:
    return float(cost_gflops) * float(ms_per_gflop)


def apply_decision_rule(
    rows: Sequence[Mapping[str, Any]],
    reference: str,
    tie_delta: float,
    max_latency_ms: float,
    min_gain_auprc: float,
) -> dict[str, Any]:
    """Regla prerregistrada de F3b.3 sobre una tabla de candidatos.

    Cada fila: ``name``, ``auroc``, ``auprc``, ``spec_at_sens090``, ``latency_ms``.

    1. Orden por AUPRC y después por spec@sens0.90.
    2. Empate: |ΔAUC-ROC| < ``tie_delta`` **y** |ΔAUPRC| < ``tie_delta`` respecto al líder;
       entre empatados gana el más barato (menor latencia).
    3. Restricción dura: ``latency_ms`` < ``max_latency_ms``; quien la viole queda fuera.
    4. Si ninguna combinación factible supera a la referencia por más de ``min_gain_auprc`` en
       AUPRC, el ensamble no aporta: ``winner`` es la referencia y ``ensemble_helps`` es False.
    """
    by_name = {r["name"]: r for r in rows}
    if reference not in by_name:
        raise ValueError(f"la referencia {reference!r} no está en la tabla")
    ref = by_name[reference]
    feasible = [r for r in rows if float(r["latency_ms"]) < max_latency_ms]
    infeasible = [r["name"] for r in rows if r not in feasible]
    ranked = sorted(
        feasible, key=lambda r: (-float(r["auprc"]), -float(r["spec_at_sens090"]), r["name"])
    )
    if not ranked:
        raise ValueError("ningún candidato cumple la restricción de latencia")
    leader = ranked[0]
    tied = [
        r
        for r in ranked
        if abs(float(r["auroc"]) - float(leader["auroc"])) < tie_delta
        and abs(float(r["auprc"]) - float(leader["auprc"])) < tie_delta
    ]
    winner = min(tied, key=lambda r: (float(r["latency_ms"]), r["name"]))
    best_gain = max(float(r["auprc"]) - float(ref["auprc"]) for r in feasible)
    ensemble_helps = best_gain > min_gain_auprc and winner["name"] != reference
    return {
        "reference": reference,
        "ranking": [r["name"] for r in ranked],
        "infeasible": infeasible,
        "leader": leader["name"],
        "tied_with_leader": [r["name"] for r in tied],
        "winner": winner["name"] if ensemble_helps else reference,
        "winner_by_rules_1_to_3": winner["name"],
        "winner_gain_auprc": float(winner["auprc"]) - float(ref["auprc"]),
        "best_gain_auprc": best_gain,
        "min_gain_auprc": min_gain_auprc,
        "ensemble_helps": bool(ensemble_helps),
    }


def pareto_frontier(points: Sequence[tuple[float, float]]) -> list[int]:
    """Índices de los puntos (costo, métrica) no dominados: nadie es más barato y mejor."""
    idx = sorted(range(len(points)), key=lambda i: (points[i][0], -points[i][1]))
    frontier, best = [], -np.inf
    for i in idx:
        if points[i][1] > best:
            frontier.append(i)
            best = points[i][1]
    return frontier


# ---- apilador de metadatos (F3b.4) ------------------------------------------------------------
LOGIT_COLUMN = "logit_ensemble"


def stacker_frame(
    frame: pd.DataFrame, logit: np.ndarray, numeric: Sequence[str], categorical: Sequence[str]
) -> pd.DataFrame:
    """Diseño del apilador: logit del ensamble + las variables de B0, en una tabla."""
    out = frame[list(numeric) + list(categorical)].copy().reset_index(drop=True)
    out.insert(0, LOGIT_COLUMN, np.asarray(logit, dtype=np.float64))
    return out


def build_stacker(
    numeric: Sequence[str],
    categorical: Sequence[str],
    impute_numeric: str,
    missing_category: str,
    Cs: Sequence[float],
    inner_splits: int,
    scoring: str,
    max_iter: int,
    seed: int,
    groups: np.ndarray | None = None,
) -> Pipeline:
    """Regresión logística L2 con C elegido por VC interna (agrupada por paciente si se pasan
    ``groups``). El logit del ensamble entra sin escalar: su coeficiente es interpretable
    (1.0 = «el apilador no toca al ensamble»)."""
    pre = ColumnTransformer(
        [
            ("logit", "passthrough", [LOGIT_COLUMN]),
            (
                "num",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy=impute_numeric, add_indicator=True)),
                        ("scale", StandardScaler()),
                    ]
                ),
                list(numeric),
            ),
            (
                "cat",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="constant", fill_value=missing_category)),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                list(categorical),
            ),
        ]
    )
    if groups is None:
        inner = inner_splits
    else:
        inner = list(
            GroupKFold(n_splits=inner_splits, shuffle=True, random_state=seed).split(
                np.zeros(len(groups)), groups=groups
            )
        )
    clf = LogisticRegressionCV(
        Cs=list(Cs), cv=inner, scoring=scoring, penalty="l2", max_iter=max_iter, refit=True
    )
    return Pipeline([("pre", pre), ("clf", clf)])


def grouped_folds(
    groups: np.ndarray, n_splits: int, seed: int
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Pliegues agrupados por paciente: ningún paciente cae en entrenamiento y prueba a la vez."""
    g = np.asarray(groups).astype(str)
    splitter = GroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    return list(splitter.split(np.zeros(len(g)), groups=g))


def folds_are_grouped(folds: Sequence[tuple[np.ndarray, np.ndarray]], groups: np.ndarray) -> bool:
    g = np.asarray(groups).astype(str)
    return all(not (set(g[tr]) & set(g[te])) for tr, te in folds)


def stacker_cv_logits(
    pipe_factory,
    X: pd.DataFrame,
    y: np.ndarray,
    groups: np.ndarray,
    folds: Sequence[tuple[np.ndarray, np.ndarray]],
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    """Logits fuera de pliegue del apilador (``decision_function``) y el C elegido por pliegue.

    ``pipe_factory(groups_train)`` devuelve el pipeline; la VC interna del C también se agrupa.
    """
    oof = np.full(len(y), np.nan, dtype=np.float64)
    chosen = []
    for k, (tr, te) in enumerate(folds):
        pipe = pipe_factory(np.asarray(groups)[tr])
        pipe.fit(X.iloc[tr], y[tr])
        oof[te] = pipe.decision_function(X.iloc[te])
        chosen.append(
            {
                "fold": k,
                "C": float(pipe.named_steps["clf"].C_[0]),
                "n_train": int(len(tr)),
                "n_eval": int(len(te)),
                "positives_eval": int(y[te].sum()),
            }
        )
    if np.isnan(oof).any():
        raise RuntimeError("quedaron imágenes sin predicción fuera de pliegue")
    return oof, chosen


def frozen_stacker(pipe: Pipeline) -> dict[str, Any]:
    """Serializa el apilador ajustado sin pickles: nombres de columnas, preprocesamiento y pesos.
    ``apply_frozen_stacker`` reconstruye ``decision_function`` exactamente."""
    pre: ColumnTransformer = pipe.named_steps["pre"]
    clf = pipe.named_steps["clf"]
    num = pre.named_transformers_["num"]
    cat = pre.named_transformers_["cat"]
    imputer: SimpleImputer = num.named_steps["impute"]
    scaler: StandardScaler = num.named_steps["scale"]
    onehot: OneHotEncoder = cat.named_steps["onehot"]
    numeric_cols = list(pre.transformers_[1][2])
    categorical_cols = list(pre.transformers_[2][2])
    return {
        "enabled": True,
        "model": "logistic_regression_l2",
        "C": float(clf.C_[0]),
        "features": [n.split("__", 1)[1] for n in pre.get_feature_names_out()],
        "coefficients": [float(c) for c in clf.coef_.ravel()],
        "intercept": float(clf.intercept_[0]),
        "numeric": {
            "columns": numeric_cols,
            "impute_values": [float(v) for v in imputer.statistics_],
            "indicator_columns": [numeric_cols[int(i)] for i in imputer.indicator_.features_]
            if imputer.indicator_ is not None
            else [],
            "scale_mean": [float(v) for v in scaler.mean_],
            "scale_std": [float(v) for v in scaler.scale_],
        },
        "categorical": {
            "columns": categorical_cols,
            "missing_category": str(cat.named_steps["impute"].fill_value),
            "categories": [[str(c) for c in cats] for cats in onehot.categories_],
        },
    }


def apply_frozen_stacker(
    spec: Mapping[str, Any], frame: pd.DataFrame, logit: np.ndarray
) -> np.ndarray:
    """``decision_function`` del apilador congelado, reconstruida a mano desde el protocolo."""
    cols = [np.asarray(logit, dtype=np.float64)]
    num, cat = spec["numeric"], spec["categorical"]
    raw = [frame[c].to_numpy(dtype=np.float64) for c in num["columns"]]
    filled = [
        np.where(np.isnan(v), fill, v) for v, fill in zip(raw, num["impute_values"], strict=True)
    ]
    indicators = [
        np.isnan(frame[c].to_numpy(dtype=np.float64)).astype(np.float64)
        for c in num["indicator_columns"]
    ]
    scaled_in = filled + indicators
    for v, m, s in zip(scaled_in, num["scale_mean"], num["scale_std"], strict=True):
        cols.append((v - m) / s)
    for c, cats in zip(cat["columns"], cat["categories"], strict=True):
        values = (
            frame[c]
            .astype(object)
            .where(frame[c].notna(), cat["missing_category"])
            .astype(str)
            .to_numpy()
        )
        for category in cats:
            cols.append((values == category).astype(np.float64))
    X = np.column_stack(cols)
    coef = np.asarray(spec["coefficients"], dtype=np.float64)
    if X.shape[1] != coef.size:
        raise ValueError(
            f"el diseño tiene {X.shape[1]} columnas y el protocolo {coef.size} coeficientes"
        )
    return X @ coef + float(spec["intercept"])
