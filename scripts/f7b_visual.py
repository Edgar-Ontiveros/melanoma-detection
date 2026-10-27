# ruff: noqa: E501
"""F7b.5 — `reports/f7b_visual.md`: tabla de contraste WCAG de cada par texto/fondo de los
tokens (todas ≥ 4.5:1, o ≥ 3:1 si el texto es ≥ 24 px) y la lista de capturas de
`make f7-screenshots`. Los colores se leen de services/web/src/styles/tokens.css.

Uso: uv run python scripts/f7b_visual.py
"""

from __future__ import annotations

import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKENS = ROOT / "services" / "web" / "src" / "styles" / "tokens.css"
OUT = ROOT / "reports" / "f7b_visual.md"
FIGURES = ROOT / "reports" / "figures"

# (texto, fondo, dónde se usa, ¿texto grande ≥ 24 px?)
PAIRS = [
    ("--text", "--bg", "cuerpo, títulos, tablas", False),
    ("--text", "--surface", "zona de carga, detalles, pie, recomendación bajo el umbral", False),
    ("--text-2", "--bg", "subtítulos, etiquetas, ayuda, intervalos", False),
    ("--text-2", "--surface", "ayuda en tarjetas con superficie, pie", False),
    ("--accent", "--bg", "enlaces, botón fantasma, subrayado activo", False),
    ("--accent-hover", "--bg", "enlaces al pasar", False),
    ("--on-accent", "--accent", "botón primario", False),
    ("--on-accent", "--accent-hover", "botón primario al pasar", False),
    ("--accent-hover", "--accent-tint", "etiqueta «Recomendación» sobre el tinte", False),
    ("--accent", "--accent-tint", "enlaces y acento sobre el tinte", False),
    ("--text", "--accent-tint", "texto de la recomendación por encima del umbral", False),
    ("--text-2", "--accent-tint", "segunda línea de la recomendación", False),
    ("--text", "--bg", "probabilidad a 52/64 px", True),
]
# Sin texto encima (no se evalúan como texto): --accent-bright en el subrayado activo, el relleno
# de la barra y las marcas; --signature en la franja de 4 px; los logos son imágenes.


def read_tokens() -> dict[str, str]:
    text = TOKENS.read_text(encoding="utf-8")
    return dict(re.findall(r"(--[a-z0-9-]+):\s*(#[0-9a-fA-F]{6});", text))


def luminance(hex_color: str) -> float:
    r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5))

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(fg: str, bg: str) -> float:
    a, b = luminance(fg), luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def main() -> None:
    tokens = read_tokens()
    rows, all_ok = [], True
    for fg, bg, use, large in PAIRS:
        ratio = contrast(tokens[fg], tokens[bg])
        minimum = 3.0 if large else 4.5
        ok = ratio >= minimum
        all_ok &= ok
        rows.append(
            f"| `{fg}` {tokens[fg]} | `{bg}` {tokens[bg]} | {use} | {ratio:.2f}:1 | {minimum:.1f}:1 | {'sí' if ok else '**no**'} |"
        )
    shots = sorted(p.name for p in FIGURES.glob("f7_ui_*.png"))
    md = [
        "# F7b — Sistema visual: contraste y capturas",
        "",
        f"Generado por `scripts/f7b_visual.py` el {time.strftime('%Y-%m-%d')} desde `services/web/src/styles/tokens.css`. Contraste según WCAG 2.1 (AA: ≥ 4.5:1 para texto normal, ≥ 3:1 para texto ≥ 24 px).",
        "",
        "## Contraste de los tokens",
        "",
        "| texto | fondo | uso | razón | mínimo | cumple |",
        "|:--|:--|:--|--:|--:|:--|",
        *rows,
        "",
        f"**{'Todos los pares cumplen AA.' if all_ok else 'Hay pares que NO cumplen AA.'}** Los bordes (`--border`, `--border-strong`) no llevan texto; el anillo de foco es `--accent` sobre `--bg` con 2 px de separación.",
        "",
        "## Capturas",
        "",
        "Tomadas con `make f7-screenshots` (Playwright, Chromium) contra la demo local, a 1440 px (escritorio) y 390 px (teléfono): análisis vacío y con resultado, ficha del modelo y aviso.",
        "",
        *[f"- `reports/figures/{s}`" for s in shots],
        "",
        "![Análisis, escritorio](figures/f7_ui_analisis_resultado_1440.png)",
        "",
        "![Ficha del modelo, escritorio](figures/f7_ui_modelo_1440.png)",
        "",
    ]
    OUT.write_text("\n".join(md), encoding="utf-8")
    print(f"→ {OUT.relative_to(ROOT)} · {len(rows)} pares · AA: {'sí' if all_ok else 'NO'}")
    if not all_ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
