# ruff: noqa: E501
"""F3b.6 — `reports/f3b_ensemble.md`, seis secciones en el orden de la spec, a partir de
reports/f3b_ensemble.json (scripts/f3b_ensemble.py) y reports/f3b_checkpoints.json
(scripts/f3b_logits.py). Solo validación."""

from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENSEMBLE = ROOT / "reports" / "f3b_ensemble.json"
OUT = ROOT / "reports" / "f3b_ensemble.md"


def fmt(x, d=3):
    return "n/d" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{d}f}"


def ci(d: dict, key: str, d_=3) -> str:
    c = d["ci"][key]
    return f"{fmt(c['point'], d_)} [{fmt(c['lo'], d_)}, {fmt(c['hi'], d_)}]"


def section_checkpoints(r: dict) -> list[str]:
    ck = r["checkpoints"]
    lines = [
        "## 1. Verificación de los nueve checkpoints contra F3",
        "",
        f"Checkpoints bajados de las salidas de los kernels de F3 en Kaggle a `data/models/` (fuera de git) y evaluados sobre validación en CPU ({r['n_images']:,} imágenes, {r['n_positives']} melanomas, {r['n_patients']} pacientes). Criterio: |ΔAUC-ROC| < {ck['auroc_tolerance']} respecto al `metrics.json` de la corrida (los valores que promedia `reports/f3_matrix.md`).",
        "",
        "| corrida | archivo | SHA256 | MB | AUC-ROC corrida | AUC-ROC local | Δ | usado |",
        "|:--|:--|:--|--:|--:|--:|--:|:--|",
    ]
    for m in ck["members"]:
        lines.append(
            f"| {m['run']} | `{m['file']}` | `{m['sha256'][:16]}…` | {m['bytes'] / 1e6:.1f} | {fmt(m['auroc_run'], 4)} | {fmt(m['auroc_reproduced'], 4)} | {m['auroc_diff']:+.4f} | {'sí' if m['ok'] else '**no: excluido**'} |"
        )
    lines += [
        "",
        f"{ck['n_ok']}/{len(ck['members'])} checkpoints reproducen su AUC; excluidos: {', '.join(ck['excluded']) or 'ninguno'}. Logits en caché: `reports/predictions/f3b_val_logits.npz` (SHA256 `{(ck.get('logits_npz_sha256') or '')[:16]}…`), forma [{len(ck['members'])}, {len(r['checkpoints']['views'])}, {r['n_images']}], vistas {', '.join(r['checkpoints']['views'])}.",
    ]
    return lines


def section_candidates(r: dict) -> list[str]:
    d, dp = r["decision"], r["decision_params"]
    anchor = r["latency_anchor"]
    lines = [
        "## 2. Las combinaciones: ensamble × TTA",
        "",
        f"Ensamble = promedio de **logits**. Costo = GFLOPs por imagen × vistas; latencia extrapolada de F6 ({anchor['gflops']} GFLOPs ≈ {anchor['ms']:.0f} ms de ONNX en la laptop). IC 95 % por bootstrap a nivel paciente ({r['decision_params'].get('bootstrap_resamples', '')}{''}2,000 remuestreos). Ordenadas por AUPRC; **Eᵍ en negritas**; las que violan el límite de {dp['max_latency_ms']:.0f} ms quedan tachadas.",
        "",
        "| combinación | modelos | vistas | AUC-ROC | AUPRC | spec@sens0.90 | spec@sens0.95 | GFLOPs | ≈ ms | factible |",
        "|:--|:--|:--|:--|:--|:--|:--|--:|--:|:--|",
    ]
    for c in sorted(r["candidates"], key=lambda c: -c["auprc"]):
        name = (
            f"**{c['name']}**"
            if c["name"] == d["winner"]
            else (f"~~{c['name']}~~" if c["name"] in d["infeasible"] else c["name"])
        )
        if c["name"] == d["reference"]:
            name += " (ref.)"
        lines.append(
            f"| {name} | {c['label']} | {len(c['views'])} | {ci(c, 'auroc')} | {ci(c, 'auprc')} | {ci(c, 'spec_at_sens090')} | {ci(c, 'spec_at_sens095')} | {c['cost_gflops']:.1f} | {c['latency_ms']:.0f} | {'no' if c['name'] in d['infeasible'] else 'sí'} |"
        )
    ref = next(c for c in r["candidates"] if c["name"] == d["reference"])
    win = next(c for c in r["candidates"] if c["name"] == d["winner"])
    lines += [
        "",
        "### Regla de decisión aplicada (escrita antes de ver los números)",
        "",
        f"1. Orden por AUPRC y después por spec@sens0.90: líder **{d['leader']}**.",
        f"2. Empate (|ΔAUC-ROC| y |ΔAUPRC| < {dp['tie_delta']}) con el líder: {', '.join(d['tied_with_leader'])}; el más barato de ellos es {d['cheapest_tied']}.",
        f"3. Restricción dura (< {dp['max_latency_ms']:.0f} ms estimados): fuera {', '.join(d['infeasible']) or 'ninguna'}.",
        f"4. Empatados, factibles y que superan a {d['reference']} por más de {dp['min_gain_auprc']} de AUPRC: {', '.join(d['eligible']) or 'ninguno'} (mejor ganancia entre todas las factibles: {d['best_gain_auprc']:+.4f}). "
        + (
            f"**El ensamble aporta.** Eᵍ = **{d['winner']}** ({win['label']}, {len(win['views'])} vista(s)): AUPRC {win['auprc']:.3f} contra {ref['auprc']:.3f} de la referencia ({d['winner_gain_auprc']:+.3f}), AUC-ROC {win['auroc']:.3f} contra {ref['auroc']:.3f}, spec@sens0.95 {win['spec_at_sens095']:.3f} contra {ref['spec_at_sens095']:.3f}; costo {win['cost_gflops']:.1f} GFLOPs ≈ {win['latency_ms']:.0f} ms."
            if d["ensemble_helps"]
            else f"**El ensamble no aporta** con estos datos: ningún candidato empatado con el líder y factible supera a la referencia por más de {dp['min_gain_auprc']} de AUPRC. F4b no se ejecuta y el acceso de reserva se conserva. Eᵍ = {d['reference']} (el modelo único de F4)."
        ),
    ]
    return lines


def _figure_ref(figure: str) -> str:
    p = Path(figure)
    return p.relative_to("reports").as_posix() if p.is_relative_to("reports") else p.name


def section_figure(r: dict) -> list[str]:
    return [
        "## 3. AUPRC contra costo",
        "",
        f"![AUPRC contra costo]({_figure_ref(r['figure'])})",
        "",
        "Frontera: ninguna combinación es a la vez más barata y mejor que las de la línea. La línea punteada es el límite de latencia.",
    ]


def section_stacker(r: dict) -> list[str]:
    s = r["stacker"]
    g, rule, pooled = s["gain"], s["rule"], s["pooled_out_of_fold"]
    lines = [
        "## 4. Metadatos apilados",
        "",
        f"Regresión logística L2 sobre el logit de Eᵍ más {', '.join(s['features']['numeric'])} (estandarizada, con indicador de faltante) y {', '.join(s['features']['categorical'])} (one-hot con faltante). C elegido por VC interna agrupada por paciente ({s['inner_splits']} pliegues, `{s['scoring']}`, C ∈ {s['Cs']}); evaluación por VC externa de {s['outer_splits']} pliegues agrupada por paciente, comparando las predicciones fuera de pliegue del apilador con Eᵍ solo sobre las mismas imágenes.",
        "",
        "| | AUC-ROC | AUPRC | spec@sens0.95 |",
        "|:--|:--|:--|:--|",
        f"| Eᵍ solo | {ci(pooled['winner'], 'auroc')} | {ci(pooled['winner'], 'auprc')} | {ci(pooled['winner'], 'spec_at_sens095')} |",
        f"| Eᵍ + metadatos (fuera de pliegue) | {ci(pooled['stacker'], 'auroc')} | {ci(pooled['stacker'], 'auprc')} | {ci(pooled['stacker'], 'spec_at_sens095')} |",
        f"| ganancia | {g['auroc']:+.4f} | {g['auprc']:+.4f} | {g['spec_at_sens095']:+.4f} |",
        "",
        "| pliegue | n | melanomas | AUC Eᵍ | AUC apilador | spec@95 Eᵍ | spec@95 apilador | C |",
        "|--:|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for pf, c in zip(s["per_fold"], s["chosen_C_per_fold"], strict=True):
        lines.append(
            f"| {pf['fold']} | {pf['n']} | {pf['positives']} | {fmt(pf['auroc_winner'])} | {fmt(pf['auroc_stacker'])} | {fmt(pf['spec_at_sens095_winner'])} | {fmt(pf['spec_at_sens095_stacker'])} | {c['C']:g} |"
        )
    verdict = (
        f"**Se despliegan**: la VC muestra ΔAUC-ROC {g['auroc']:+.3f} (umbral ≥ {rule['min_gain_auroc']}) o Δspec@sens0.95 {g['spec_at_sens095']:+.3f} (umbral ≥ {rule['min_gain_spec_at_sens095']}). El apilador final se ajustó sobre toda la validación (C = {s['frozen']['C']:g}) y va en el protocolo; en la API los metadatos son opcionales."
        if s["deploy"]
        else f"**No se despliegan**: la ganancia medida (ΔAUC-ROC {g['auroc']:+.3f}, Δspec@sens0.95 {g['spec_at_sens095']:+.3f}) no alcanza el umbral (≥ +{rule['min_gain_auroc']} en AUC-ROC o ≥ +{rule['min_gain_spec_at_sens095']} en spec@sens0.95). El modelo final de F3b es Eᵍ solo y la interfaz no pide metadatos."
    )
    lines += ["", "### Decisión", "", verdict]
    return lines


def section_calibration(r: dict) -> list[str]:
    f = r["final"]
    pl, cal, th = f["platt"], f["calibration"], f["thresholds"]
    lines = [
        "## 5. Calibración y umbrales del modelo final de F3b",
        "",
        f"Modelo: **{f['model']}**. Platt sobre {'la salida del apilador' if 'apilador' in f['model'] else 'el logit del ensamble'}: a = {pl['a']:.4f}, b = {pl['b']:.4f}. Brier {cal['raw']['brier']:.4f} → {cal['platt']['brier']:.4f}; ECE (10 bins uniformes) {cal['raw']['ece_uniform']['ece']:.4f} → {cal['platt']['ece_uniform']['ece']:.4f}.",
        "",
        "| umbral | τ (mediana) | p5 | p95 | corte único | sens | spec | VPP | VPN |",
        "|:--|--:|--:|--:|--:|--:|--:|--:|--:|",
    ]
    for k in ("tau_95", "tau_90"):
        t = th[k]
        o = t["on_full_set"]
        lines.append(
            f"| {k.replace('tau_', 'τ')} (sens ≥ {t['sensitivity_target']:.2f}) | {t['tau']:.5f} | {t['p05']:.5f} | {t['p95']:.5f} | {t['single_cut']:.5f} | {o['sensitivity']:.3f} | {o['specificity']:.3f} | {o['ppv']:.3f} | {o['npv']:.4f} |"
        )
    lines += [
        "",
        f"Sobre validación con Platt: AUC-ROC {ci(f, 'auroc')}, AUPRC {ci(f, 'auprc')}, spec@sens0.95 {ci(f, 'spec_at_sens095')}. Bootstrap por paciente, {th['tau_95']['n_resamples']:,} remuestreos, semilla {th['tau_95']['seed']}.",
        "",
        f"> **Advertencia de optimismo.** {f['optimism_warning']}",
    ]
    return lines


def section_final(r: dict) -> list[str]:
    d, f = r["decision"], r["final"]
    win = next(c for c in r["candidates"] if c["name"] == d["winner"])
    by_run = {m["run"]: m for m in r["checkpoints"]["members"]}
    lines = ["## 6. Declaración del modelo final de F3b", ""]
    if not d["ensemble_helps"]:
        lines += [
            f"El ensamble no aporta (sección 2). El modelo final sigue siendo el de F4 (`{d['reference']}`), con su protocolo `docs/f4_protocol.yaml` intacto. **F4b no se ejecuta**; el segundo acceso al conjunto de prueba se conserva.",
            "",
        ]
    lines += [
        f"- Combinación: **{d['winner']}** — {win['label']}; ensamble por promedio de logits; vistas de TTA: {', '.join(win['views'])}; costo {win['cost_gflops']:.1f} GFLOPs ≈ {win['latency_ms']:.0f} ms.",
        f"- Apilador de metadatos: {'sí (C = ' + format(r['stacker']['frozen']['C'], 'g') + ')' if r['stacker']['deploy'] else 'no'}.",
        f"- Platt a = {f['platt']['a']:.6f}, b = {f['platt']['b']:.6f}; τ95 = {f['thresholds']['tau_95']['tau']:.6f}; τ90 = {f['thresholds']['tau_90']['tau']:.6f}.",
        f"- Logits de validación: `reports/predictions/f3b_val_logits.npz`, SHA256 `{r['checkpoints'].get('logits_npz_sha256', '')}`.",
        f"- Protocolo de F4b: `docs/f4b_protocol.yaml`{' (escrito desde estos valores)' if d['ensemble_helps'] else ' (no se escribe: F4b no corre)'}.",
        "",
        "| miembro | archivo | SHA256 |",
        "|:--|:--|:--|",
    ]
    for m in win["members"]:
        lines.append(f"| {m} | `{by_run[m]['file']}` | `{by_run[m]['sha256']}` |")
    return lines


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="F3b.6: reporte del ensamble")
    ap.add_argument("--ensemble", default=str(ENSEMBLE))
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    out = Path(args.out)
    r = json.loads(Path(args.ensemble).read_text(encoding="utf-8"))
    parts = [
        "# F3b — Ensamble, TTA y metadatos sobre validación",
        "",
        f"Generado por `scripts/f3b_report.py` el {r['date']} (commit `{r['git_sha']}`) a partir de `reports/f3b_ensemble.json`. Todo se decidió sobre validación; el split de prueba no se tocó. Spec: `docs/specs/F3b-F4b.md`.",
        "",
        *section_checkpoints(r),
        "",
        *section_candidates(r),
        "",
        *section_figure(r),
        "",
        *section_stacker(r),
        "",
        *section_calibration(r),
        "",
        *section_final(r),
        "",
    ]
    out.write_text("\n".join(parts), encoding="utf-8")
    print(
        f"→ {out}: Eᵍ = {r['decision']['winner']}, apilador {'sí' if r['stacker']['deploy'] else 'no'}"
    )


if __name__ == "__main__":
    main()
