"""F3b: el ensamble promedia logits, las vistas de TTA son involuciones, la VC del apilador se
agrupa por paciente y la regla de decisión prerregistrada se aplica tal como está escrita."""

from __future__ import annotations

import numpy as np
import pytest
import torch

from melanoma.eval.ensemble import (
    VIEW_FLIPS,
    apply_decision_rule,
    apply_view,
    folds_are_grouped,
    grouped_folds,
    mean_logits,
    sigmoid,
)


def test_ensemble_mean_logits() -> None:
    """El promedio es de logits, no de probabilidades: con logits asimétricos los dos difieren."""
    z = np.zeros((2, 1, 3))
    z[0, 0] = [4.0, -4.0, 0.0]
    z[1, 0] = [-2.0, 2.0, 1.0]
    got = mean_logits(z, [0, 1], [0])
    np.testing.assert_allclose(got, [1.0, -1.0, 0.5])
    prob_mean = sigmoid(z[:, 0, :]).mean(axis=0)
    assert not np.allclose(sigmoid(got), prob_mean), "promediar probabilidades daría otra cosa"
    # Subconjuntos de miembros y vistas respetan los índices pedidos.
    z3 = np.arange(2 * 2 * 2, dtype=float).reshape(2, 2, 2)
    np.testing.assert_allclose(mean_logits(z3, [1], [0, 1]), z3[1].mean(axis=0))
    with pytest.raises(ValueError):
        mean_logits(np.zeros((3, 4)), [0], [0])


def test_tta_views_are_involutions() -> None:
    """Espejar dos veces devuelve la imagen original; cada volteo no trivial cambia la imagen."""
    x = torch.arange(2 * 3 * 5 * 7, dtype=torch.float32).reshape(2, 3, 5, 7)
    for view in VIEW_FLIPS:
        assert torch.equal(apply_view(apply_view(x, view), view), x), view
        if view != "identity":
            assert not torch.equal(apply_view(x, view), x), view
    assert torch.equal(apply_view(x, "hvflip"), apply_view(apply_view(x, "hflip"), "vflip"))
    with pytest.raises(ValueError):
        apply_view(x, "rot90")


def test_stacker_cv_grouped_by_patient() -> None:
    """Ningún paciente aparece en entrenamiento y prueba del mismo pliegue; cada imagen se evalúa
    exactamente una vez."""
    rng = np.random.default_rng(0)
    patients = np.array([f"P{i:03d}" for i in rng.integers(0, 60, size=300)])
    folds = grouped_folds(patients, n_splits=5, seed=20260904)
    assert len(folds) == 5
    assert folds_are_grouped(folds, patients)
    evaluated = np.concatenate([te for _, te in folds])
    assert sorted(evaluated.tolist()) == list(range(300))
    # Un pliegue ingenuo por imagen sí mezcla pacientes: la verificación lo detecta.
    naive = [(np.arange(0, 150), np.arange(150, 300))]
    assert not folds_are_grouped(naive, patients)


def _row(name, auroc, auprc, spec90, ms):
    return {
        "name": name,
        "auroc": auroc,
        "auprc": auprc,
        "spec_at_sens090": spec90,
        "latency_ms": ms,
    }


def test_decision_rule_f3b() -> None:
    """Eᵍ es el más barato de los que empatan con el líder, cumplen el costo y superan a E0 por
    más de 0.02 de AUPRC; quien viola el costo queda fuera aunque gane; conjunto vacío → el
    ensamble no aporta."""
    rows = [
        _row("E0/none", 0.830, 0.130, 0.44, 30),
        _row("E1/tta2", 0.845, 0.165, 0.50, 180),  # empata con el líder, más barato, supera a E0
        _row("E2/tta2", 0.850, 0.170, 0.52, 990),  # líder factible
        _row("E3/tta4", 0.880, 0.250, 0.60, 3000),  # el mejor, pero viola el costo
    ]
    d = apply_decision_rule(
        rows, "E0/none", tie_delta=0.02, max_latency_ms=1000, min_gain_auprc=0.02
    )
    assert d["infeasible"] == ["E3/tta4"]
    assert d["leader"] == "E2/tta2"
    assert set(d["tied_with_leader"]) == {"E2/tta2", "E1/tta2"}
    assert d["winner"] == "E1/tta2" and d["ensemble_helps"]
    # El más barato de los empatados NO supera a E0 por más de 0.02; el siguiente sí → gana el
    # siguiente, no la referencia ni el barato.
    close = [
        _row("E0/none", 0.830, 0.130, 0.44, 30),
        _row("E1/tta2", 0.846, 0.148, 0.50, 180),  # empatado y barato, pero +0.018 sobre E0
        _row("E2/tta2", 0.850, 0.165, 0.52, 990),  # líder: +0.035 sobre E0
    ]
    d1 = apply_decision_rule(close, "E0/none", 0.02, 1000, 0.02)
    assert d1["cheapest_tied"] == "E1/tta2"
    assert d1["eligible"] == ["E2/tta2"]
    assert d1["winner"] == "E2/tta2" and d1["ensemble_helps"]
    assert d1["winner_gain_auprc"] == pytest.approx(0.035)
    # Sin ganancia suficiente sobre la referencia: el conjunto queda vacío y no aporta.
    flat = [
        _row("E0/none", 0.830, 0.130, 0.44, 30),
        _row("E1/tta2", 0.835, 0.145, 0.46, 180),
    ]
    d2 = apply_decision_rule(flat, "E0/none", 0.02, 1000, 0.02)
    assert not d2["ensemble_helps"] and d2["winner"] == "E0/none" and d2["eligible"] == []
    with pytest.raises(ValueError):
        apply_decision_rule(rows, "E9", 0.02, 1000, 0.02)
