# ruff: noqa: E501
"""F7b.3 — Símbolo «lente» y favicons de la interfaz, generados desde un solo dibujo.

Anillo ``circle cx=16 cy=16 r=11`` con trazo 3 sin relleno y punto ``circle cx=19.5 cy=19.5 r=4``
relleno, en un viewBox de 32 × 32. Produce en ``services/web/public/``: ``mark.svg``
(currentColor, para el encabezado), ``favicon.svg`` (acento sobre transparente; en modo oscuro
cambia a un azul claro), ``favicon.ico`` (16 y 32 px) y ``apple-touch-icon.png`` (180 px, símbolo
sobre blanco con 20 % de margen). Los PNG/ICO se rasterizan con Pillow con supermuestreo ×8.

Uso: uv run python scripts/f7b_icons.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "services" / "web" / "public"
ACCENT = (11, 110, 153)  # --accent #0B6E99 (tokens.css, F7b.6)
ACCENT_DARK = "#5FB8E6"
RING = (16.0, 16.0, 11.0, 3.0)  # cx, cy, r, trazo
DOT = (19.5, 19.5, 4.0)  # cx, cy, r
SS = 8  # supermuestreo


def svg(color: str | None, dark: str | None = None) -> str:
    """SVG del símbolo. ``color=None`` → currentColor (hereda del texto, para el encabezado);
    con un color fijo y ``dark``, un ``<style>`` cambia el color en modo oscuro (favicon)."""
    style = ""
    if color is not None:
        dark_rule = f"@media (prefers-color-scheme: dark){{svg{{color:{dark}}}}}" if dark else ""
        style = f"<style>svg{{color:{color}}}{dark_rule}</style>"
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" role="img" aria-label="Detección asistida de melanoma">'
        + style
        + f'<circle cx="{RING[0]}" cy="{RING[1]}" r="{RING[2]}" fill="none" stroke="currentColor" stroke-width="{RING[3]}"/>'
        + f'<circle cx="{DOT[0]}" cy="{DOT[1]}" r="{DOT[2]}" fill="currentColor"/>'
        + "</svg>\n"
    )


def raster(size: int, margin_frac: float, background: tuple | None) -> Image.Image:
    """Símbolo centrado en ``size`` px con ``margin_frac`` de margen por lado."""
    big = size * SS
    img = Image.new("RGBA", (big, big), background + (255,) if background else (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    inner = big * (1 - 2 * margin_frac)
    off = big * margin_frac
    k = inner / 32.0
    cx, cy, r, w = RING
    d.ellipse(
        [off + (cx - r) * k, off + (cy - r) * k, off + (cx + r) * k, off + (cy + r) * k],
        outline=ACCENT + (255,),
        width=max(1, round(w * k)),
    )
    dx, dy, dr = DOT
    d.ellipse(
        [off + (dx - dr) * k, off + (dy - dr) * k, off + (dx + dr) * k, off + (dy + dr) * k],
        fill=ACCENT + (255,),
    )
    return img.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "mark.svg").write_text(svg(None), encoding="utf-8")
    (OUT / "favicon.svg").write_text(svg("#0B6E99", ACCENT_DARK), encoding="utf-8")
    icons = [raster(s, 0.0, None) for s in (16, 32)]
    icons[1].save(
        OUT / "favicon.ico", format="ICO", sizes=[(16, 16), (32, 32)], append_images=[icons[0]]
    )
    raster(180, 0.2, (255, 255, 255)).convert("RGB").save(
        OUT / "apple-touch-icon.png", format="PNG", optimize=True
    )
    for name in ("mark.svg", "favicon.svg", "favicon.ico", "apple-touch-icon.png"):
        print(f"→ {(OUT / name).relative_to(ROOT)} ({(OUT / name).stat().st_size} B)")


if __name__ == "__main__":
    main()
