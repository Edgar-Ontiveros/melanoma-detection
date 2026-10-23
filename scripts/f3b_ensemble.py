# ruff: noqa: E501
"""F3b.3, F3b.4 y F3b.5 — Candidatos de ensamble, apilador de metadatos, calibración y umbrales.

Opera solo sobre los logits en caché de validación (`reports/predictions/f3b_val_logits.npz`,
F3b.2); no hay inferencia ni ninguna lectura del split de prueba. Salidas:
`reports/f3b_ensemble.json` (todo lo que consume `scripts/f3b_report.py`), la figura
AUPRC × costo y `docs/f4b_protocol.yaml`, el protocolo congelado del segundo acceso. El
protocolo debe commitearse antes de cualquier cambio a `scripts/evaluate_test.py`.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import hydra
import matplotlib
import numpy as np
import pandas as pd
from omegaconf import DictConfig, OmegaConf

from melanoma.data import read_manifest, resolve_paths
from melanoma.data.datamodule import VAL_SPLIT, read_split_ids, verify_split_hashes
from melanoma.eval import (
    bootstrap_patient,
    bootstrap_threshold,
    calibration_summary,
    compute_metrics,
    fit_platt,
    ppv_npv_at_prevalence,
)
from melanoma.eval.ensemble import (
    LOGIT_COLUMN,
    apply_decision_rule,
    apply_frozen_stacker,
    build_stacker,
    folds_are_grouped,
    frozen_stacker,
    grouped_folds,
    latency_ms,
    mean_logits,
    pareto_frontier,
    sigmoid,
    stacker_cv_logits,
    stacker_frame,
)
from melanoma.eval.metrics import assert_no_accuracy, auroc_auprc, specificity_at_sensitivity
from melanoma.eval.predict import split_records
from melanoma.train.run import git_sha

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from sklearn.metrics import roc_curve  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def rel(path: Path) -> str:
    """Ruta relativa al repo cuando aplica (las salidas de prueba pueden ir a otro directorio)."""
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def spec_at_sens(p: np.ndarray, y: np.ndarray, level: float) -> float:
    fpr, tpr, _ = roc_curve(y, p)
    return specificity_at_sensitivity(fpr, tpr, level)


def load_cache(path: Path) -> dict:
    z = np.load(path, allow_pickle=False)
    return {k: z[k] for k in z.files}


def candidate_table(
    f: DictConfig, cache: dict, y: np.ndarray, pid: np.ndarray, ms_per_gflop: float
) -> tuple[list[dict], dict[str, np.ndarray]]:
    members = list(cache["members"])
    excluded = set(np.asarray(cache["members"])[np.asarray(cache["excluded"], dtype=bool)])
    views = list(cache["views"])
    rows, logits_by_name = [], {}
    for cname, c in f.candidates.items():
        wanted = [str(m) for m in c.members]
        used = [m for m in wanted if m not in excluded]
        if not used:
            raise SystemExit(f"{cname}: todos sus miembros quedaron excluidos en F3b.1")
        gflops = sum(float(f.gflops_per_image[m.split("-")[0]]) for m in used)
        for tname, tviews in f.tta.items():
            tv = [str(v) for v in tviews]
            z = mean_logits(
                cache["logits"], [members.index(m) for m in used], [views.index(v) for v in tv]
            )
            p = sigmoid(z)
            cost = gflops * len(tv)
            auroc, auprc = auroc_auprc(p, y)
            ci = bootstrap_patient(p, y, pid, int(f.bootstrap_resamples), int(f.bootstrap_seed))
            name = f"{cname}/{tname}"
            rows.append(
                {
                    "name": name,
                    "candidate": str(cname),
                    "label": str(c.label),
                    "tta": tname,
                    "views": tv,
                    "members": used,
                    "members_dropped": [m for m in wanted if m in excluded],
                    "n_passes": len(used) * len(tv),
                    "gflops_per_view": gflops,
                    "cost_gflops": cost,
                    "latency_ms": latency_ms(cost, ms_per_gflop),
                    "auroc": auroc,
                    "auprc": auprc,
                    "spec_at_sens090": spec_at_sens(p, y, 0.90),
                    "spec_at_sens095": spec_at_sens(p, y, 0.95),
                    "ci": ci,
                }
            )
            logits_by_name[name] = z
    return rows, logits_by_name


def figure_auprc_cost(rows: list[dict], winner: str, max_ms: float, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4.5))
    pts = [(r["latency_ms"], r["auprc"]) for r in rows]
    front = pareto_frontier(pts)
    fx = sorted(((rows[i]["latency_ms"], rows[i]["auprc"]) for i in front), key=lambda t: t[0])
    ax.plot([a for a, _ in fx], [b for _, b in fx], "-", color="gray", lw=1, label="frontera")
    for r in rows:
        lo, hi = r["ci"]["auprc"]["lo"], r["ci"]["auprc"]["hi"]
        ax.errorbar(
            r["latency_ms"],
            r["auprc"],
            yerr=[[r["auprc"] - lo], [hi - r["auprc"]]],
            fmt="o",
            ms=5,
            color="C3" if r["name"] == winner else "C0",
            alpha=0.9,
            capsize=2,
            lw=0.8,
        )
        ax.annotate(
            r["name"],
            (r["latency_ms"], r["auprc"]),
            fontsize=6,
            textcoords="offset points",
            xytext=(3, 3),
        )
    ax.axvline(max_ms, color="C1", ls="--", lw=1, label=f"límite {max_ms:.0f} ms")
    ax.set_xscale("log")
    ax.set_xlabel("costo de inferencia estimado en CPU (ms, escala log)")
    ax.set_ylabel("AUPRC en validación (IC 95 % por paciente)")
    ax.set_title("F3b.3 — AUPRC contra costo; en rojo, Eᵍ")
    ax.legend(fontsize=8)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130)
    plt.close(fig)


def evaluate_stacker(
    f: DictConfig, recs: pd.DataFrame, z_win: np.ndarray, y: np.ndarray, pid: np.ndarray
) -> tuple[dict, dict | None]:
    s = f.stacker
    numeric, categorical = [str(c) for c in s.numeric], [str(c) for c in s.categorical]
    X = stacker_frame(recs, z_win, numeric, categorical)
    folds = grouped_folds(pid, int(s.outer_splits), int(s.seed))
    assert folds_are_grouped(folds, pid), "pliegues no agrupados por paciente"

    def factory(groups_train):
        return build_stacker(
            numeric,
            categorical,
            str(s.impute_numeric),
            str(s.missing_category),
            [float(c) for c in s.Cs],
            int(s.inner_splits),
            str(s.scoring),
            int(s.max_iter),
            int(s.seed),
            groups=groups_train,
        )

    oof, chosen = stacker_cv_logits(factory, X, y, pid, folds)
    p_stack, p_win = sigmoid(oof), sigmoid(z_win)
    per_fold = []
    for k, (_, te) in enumerate(folds):
        a_s, ap_s = auroc_auprc(p_stack[te], y[te])
        a_w, ap_w = auroc_auprc(p_win[te], y[te])
        per_fold.append(
            {
                "fold": k,
                "n": int(len(te)),
                "positives": int(y[te].sum()),
                "auroc_stacker": a_s,
                "auroc_winner": a_w,
                "auprc_stacker": ap_s,
                "auprc_winner": ap_w,
                "spec_at_sens095_stacker": spec_at_sens(p_stack[te], y[te], 0.95),
                "spec_at_sens095_winner": spec_at_sens(p_win[te], y[te], 0.95),
            }
        )
    pooled = {}
    for label, p in (("stacker", p_stack), ("winner", p_win)):
        a, ap = auroc_auprc(p, y)
        pooled[label] = {
            "auroc": a,
            "auprc": ap,
            "spec_at_sens095": spec_at_sens(p, y, 0.95),
            "ci": bootstrap_patient(p, y, pid, int(f.bootstrap_resamples), int(f.bootstrap_seed)),
        }
    gain = {
        k: pooled["stacker"][k] - pooled["winner"][k] for k in ("auroc", "auprc", "spec_at_sens095")
    }
    deploy = gain["auroc"] >= float(s.min_gain_auroc) or gain["spec_at_sens095"] >= float(
        s.min_gain_spec_at_sens095
    )
    result = {
        "features": {"numeric": numeric, "categorical": categorical, "logit": LOGIT_COLUMN},
        "outer_splits": int(s.outer_splits),
        "inner_splits": int(s.inner_splits),
        "Cs": [float(c) for c in s.Cs],
        "scoring": str(s.scoring),
        "chosen_C_per_fold": chosen,
        "per_fold": per_fold,
        "pooled_out_of_fold": pooled,
        "gain": gain,
        "rule": {
            "min_gain_auroc": float(s.min_gain_auroc),
            "min_gain_spec_at_sens095": float(s.min_gain_spec_at_sens095),
        },
        "deploy": bool(deploy),
    }
    frozen = None
    if deploy:
        pipe = factory(pid)
        pipe.fit(X, y)
        frozen = frozen_stacker(pipe)
        z_hand = apply_frozen_stacker(frozen, recs, z_win)
        z_pipe = pipe.decision_function(X)
        frozen["max_abs_reconstruction_error"] = float(np.max(np.abs(z_hand - z_pipe)))
        if frozen["max_abs_reconstruction_error"] > 1e-8:
            raise SystemExit("el apilador congelado no reproduce al pipeline")
        result["frozen"] = frozen
    return result, frozen


def write_protocol(
    f: DictConfig,
    path: Path,
    cache: dict,
    checkpoints: dict,
    winner_row: dict,
    frozen: dict | None,
    platt,
    thresholds: dict,
    decision: dict,
    stacker: dict,
) -> None:
    by_run = {m["run"]: m for m in checkpoints["members"]}
    models = [
        {
            k: by_run[m][k]
            for k in (
                "run",
                "experiment",
                "backbone",
                "image_size",
                "val_resize",
                "dropout",
                "num_classes",
                "file",
                "sha256",
                "bytes",
            )
        }
        for m in winner_row["members"]
    ]
    on_val = {
        k: {
            kk: round(float(v), 4)
            for kk, v in t["on_full_set"].items()
            if kk in ("sensitivity", "specificity", "ppv", "npv")
        }
        for k, t in thresholds.items()
    }
    f4 = OmegaConf.load(ROOT / f.f4_protocol)
    protocol = {
        "frozen_on": time.strftime("%Y-%m-%d"),
        "decided_on": "val",
        "phase": "F4b",
        "spec": "docs/specs/F3b-F4b.md",
        "winner": {
            "name": winner_row["name"],
            "label": winner_row["label"],
            "cost_gflops": winner_row["cost_gflops"],
            "latency_ms_estimated": round(winner_row["latency_ms"], 1),
            "decision_rule": {
                k: decision[k]
                for k in (
                    "reference",
                    "leader",
                    "tied_with_leader",
                    "cheapest_tied",
                    "eligible",
                    "infeasible",
                    "winner_gain_auprc",
                    "best_gain_auprc",
                    "ensemble_helps",
                )
            },
        },
        "models": models,
        "tta": list(winner_row["views"]),
        "ensemble": "logit_mean",
        "stacker": frozen if frozen else None,
        "stacker_decision": {
            "deploy": stacker["deploy"],
            "gain_auroc": stacker["gain"]["auroc"],
            "gain_spec_at_sens095": stacker["gain"]["spec_at_sens095"],
            "rule": stacker["rule"],
        },
        "calibration": {
            "method": "platt",
            "a": platt.a,
            "b": platt.b,
            "fitted_on": "val",
            "input": "stacker_logit" if frozen else "ensemble_logit",
        },
        "thresholds": {
            "method": f"bootstrap-median, {int(f.bootstrap_resamples)} resamples, patient-level, on Platt-calibrated probabilities",
            "seed": int(f.bootstrap_seed),
            "tau_95": thresholds["tau_95"]["tau"],
            "tau_90": thresholds["tau_90"]["tau"],
            "on_val": on_val,
        },
        "metrics": OmegaConf.to_container(f4.metrics),
        "ppv_npv_projection_prevalences": [float(p) for p in f.ppv_npv_projection_prevalences],
        "bootstrap": {
            "n": int(f.bootstrap_resamples),
            "unit": "patient",
            "seed": int(f.bootstrap_seed),
            "ci": 0.95,
        },
        "subgroups": OmegaConf.to_container(f4.subgroups),
        "test_access": {
            "budget_total": 2,
            "access_number": 2,
            "budget_after": 0,
            "log": str(f4.test_access.log),
        },
        "access_number": 2,
        "budget_after": 0,
        "reference_f4": {
            "protocol": str(f.f4_protocol),
            "results": str(f.f4_results_json),
            "untouched": True,
        },
        "outputs": {
            "results_json": "reports/f4b_test_results.json",
            "predictions_csv": "reports/predictions/f4b_test.csv",
            "figures_prefix": "f4b_test",
        },
        "validation_logits_sha256": checkpoints.get("logits_npz_sha256"),
    }
    header = (
        "# F4b — Protocolo congelado del segundo y último acceso al conjunto de prueba.\n"
        "# Generado por scripts/f3b_ensemble.py SOLO con validación (reports/f3b_ensemble.json).\n"
        "# Se commitea antes de ejecutar scripts/evaluate_test.py --protocol; el script se niega a\n"
        "# correr si este archivo tiene cambios sin commitear o si la bitácora ya tiene dos líneas.\n"
        "# Advertencia: validación ya se usó para elegir el ensamble, el apilador, la calibración y\n"
        "# los umbrales; su optimismo es mayor que en F4. Nada se reajusta después de ver el test.\n"
    )
    path.write_text(header + OmegaConf.to_yaml(OmegaConf.create(protocol)), encoding="utf-8")


@hydra.main(config_path="../configs", config_name="f3b", version_base="1.3")
def main(cfg: DictConfig) -> None:
    t0 = time.perf_counter()
    f = cfg.f3b
    paths = resolve_paths(cfg.data, root=ROOT)
    verify_split_hashes(paths.splits_dir)
    manifest = read_manifest(paths.manifest_path)
    recs = split_records(manifest, read_split_ids(paths.splits_dir, VAL_SPLIT))
    cache = load_cache(ROOT / f.logits_npz)
    if list(cache["image_id"]) != recs["image_id"].tolist():
        raise SystemExit("el caché de logits no está alineado con el split de validación")
    y, pid = recs["target"].to_numpy(), recs["patient_id"].to_numpy().astype(str)
    checkpoints = json.loads((ROOT / f.checkpoints_json).read_text(encoding="utf-8"))
    import hashlib

    checkpoints["logits_npz_sha256"] = hashlib.sha256(
        (ROOT / f.logits_npz).read_bytes()
    ).hexdigest()
    ms_per_gflop = float(f.decision.latency_anchor.ms) / float(f.decision.latency_anchor.gflops)

    # F3b.3
    rows, logits_by_name = candidate_table(f, cache, y, pid, ms_per_gflop)
    decision = apply_decision_rule(
        rows,
        str(f.reference),
        float(f.decision.tie_delta),
        float(f.decision.max_latency_ms),
        float(f.decision.min_gain_auprc),
    )
    winner_row = next(r for r in rows if r["name"] == decision["winner"])
    print(
        "F3b.3 —",
        "ganador",
        decision["winner"],
        "| líder",
        decision["leader"],
        "| empatados",
        decision["tied_with_leader"],
        "| fuera por costo",
        decision["infeasible"],
        f"| mejor ganancia AUPRC {decision['best_gain_auprc']:+.4f}",
    )
    for r in sorted(rows, key=lambda r: -r["auprc"]):
        print(
            f"  {r['name']:9s} AUC {r['auroc']:.4f} AUPRC {r['auprc']:.4f} spec@90 {r['spec_at_sens090']:.3f} spec@95 {r['spec_at_sens095']:.3f} costo {r['cost_gflops']:6.1f} GFLOPs ≈ {r['latency_ms']:6.0f} ms"
        )
    figure = ROOT / f.figures_dir / "f3b_auprc_vs_cost.png"
    figure_auprc_cost(rows, decision["winner"], float(f.decision.max_latency_ms), figure)

    # F3b.4
    z_win = logits_by_name[decision["winner"]]
    stacker, frozen = evaluate_stacker(f, recs, z_win, y, pid)
    g = stacker["gain"]
    print(
        f"F3b.4 — apilador por VC agrupada: ΔAUC {g['auroc']:+.4f}, ΔAUPRC {g['auprc']:+.4f}, Δspec@sens0.95 {g['spec_at_sens095']:+.4f} → {'SE DESPLIEGA' if stacker['deploy'] else 'no se despliega'}"
    )

    # F3b.5
    z_final = apply_frozen_stacker(frozen, recs, z_win) if frozen else z_win
    platt = fit_platt(z_final, y)
    p_final = platt.apply(z_final)
    thresholds = {
        f"tau_{int(round(s * 100))}": bootstrap_threshold(
            p_final, y, pid, float(s), int(f.bootstrap_resamples), int(f.bootstrap_seed)
        )
        for s in f.threshold_sensitivities
    }
    metrics_final = compute_metrics(
        p_final,
        y,
        pid,
        fixed_levels=[float(v) for v in f.fixed_levels],
        threshold=thresholds["tau_95"]["tau"],
    )
    ci_final = bootstrap_patient(p_final, y, pid, int(f.bootstrap_resamples), int(f.bootstrap_seed))
    final = {
        "model": decision["winner"] + (" + apilador de metadatos" if frozen else ""),
        "platt": platt.as_dict(),
        "calibration": {
            "raw": calibration_summary(sigmoid(z_final), y),
            "platt": calibration_summary(p_final, y),
        },
        "thresholds": thresholds,
        "metrics": {k: v for k, v in metrics_final.items() if k != "curves"},
        "ci": ci_final,
        "ppv_npv_projection_tau_95": [
            ppv_npv_at_prevalence(
                thresholds["tau_95"]["on_full_set"]["sensitivity"],
                thresholds["tau_95"]["on_full_set"]["specificity"],
                float(p),
            )
            for p in f.ppv_npv_projection_prevalences
        ],
        "optimism_warning": "Validación ya se usó para elegir Eᵍ, ajustar el apilador, calibrar y fijar el umbral. Su optimismo es mayor que en F4. El test es la única estimación limpia, y por eso existe F4b.",
    }
    assert_no_accuracy(final["metrics"])
    for k, t in thresholds.items():
        o = t["on_full_set"]
        print(
            f"F3b.5 — {k}: τ={t['tau']:.5f} [p5 {t['p05']:.5f}, p95 {t['p95']:.5f}] → sens {o['sensitivity']:.3f} spec {o['specificity']:.3f} VPP {o['ppv']:.3f} VPN {o['npv']:.4f}"
        )
    print(
        f"        Platt a={platt.a:.4f} b={platt.b:.4f}; ECE {final['calibration']['platt']['ece_uniform']['ece']:.4f}, Brier {final['calibration']['platt']['brier']:.4f}"
    )

    result = {
        "date": time.strftime("%Y-%m-%d"),
        "git_sha": git_sha(ROOT),
        "n_images": int(len(recs)),
        "n_positives": int(y.sum()),
        "n_patients": int(len(set(pid))),
        "checkpoints": checkpoints,
        "latency_anchor": {
            "gflops": float(f.decision.latency_anchor.gflops),
            "ms": float(f.decision.latency_anchor.ms),
            "ms_per_gflop": ms_per_gflop,
        },
        "decision_params": OmegaConf.to_container(f.decision),
        "candidates": rows,
        "decision": decision,
        "figure": rel(figure),
        "stacker": stacker,
        "final": final,
        "elapsed_min": (time.perf_counter() - t0) / 60,
    }
    out = ROOT / f.ensemble_json
    out.write_text(json.dumps(result, indent=2, default=float), encoding="utf-8")
    if decision["ensemble_helps"]:
        write_protocol(
            f,
            ROOT / f.protocol_yaml,
            cache,
            checkpoints,
            winner_row,
            frozen,
            platt,
            thresholds,
            decision,
            stacker,
        )
        print(
            f"→ {rel(out)}, {f.protocol_yaml} (commitear ANTES de ejecutar evaluate_test.py --protocol)"
        )
    else:
        print(
            f"→ {rel(out)}. El ensamble no aporta (regla 4): F4b no se ejecuta y no se escribe protocolo."
        )


if __name__ == "__main__":
    main()
