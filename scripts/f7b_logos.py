# ruff: noqa: E501
"""F7b.6 — Logos institucionales para la interfaz: escudo de la UACH y logo de la Facultad de
Ingeniería. Desde los originales de ``raw-assets/logos/`` (fuera del build): fondo blanco a
transparente, recorte al contenido y exportación a 2× de la altura máxima de uso (176 px) para
que se vean nítidos en pantallas de alta densidad. Salida en ``services/web/public/``.

Uso: uv run python scripts/f7b_logos.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw-assets" / "logos"
OUT = ROOT / "services" / "web" / "public"
HEIGHT = 176  # 2 × 88 px, la altura máxima de uso (72 px en /modelo, 44 px en el pie)
LOGOS = ("escudo-uach.png", "facultad-ingenieria.png")
WHITE_THRESHOLD = 245  # píxeles con R, G y B por encima → fondo


def transparent_background(img: Image.Image) -> Image.Image:
    """Vuelve transparente el fondo blanco conectado al borde (no el blanco interior del dibujo),
    con un degradado en la orilla para no dejar un halo dentado."""
    rgba = np.asarray(img.convert("RGBA")).copy()
    rgb = rgba[..., :3].astype(np.int16)
    white = (rgb.min(axis=-1) >= WHITE_THRESHOLD) & (rgba[..., 3] > 0)
    h, w = white.shape
    # relleno por inundación desde los bordes: solo el blanco conectado al exterior es fondo
    background = np.zeros_like(white)
    stack = [(y, x) for y in range(h) for x in (0, w - 1) if white[y, x]]
    stack += [(y, x) for x in range(w) for y in (0, h - 1) if white[y, x]]
    while stack:
        y, x = stack.pop()
        if background[y, x] or not white[y, x]:
            continue
        background[y, x] = True
        if y > 0:
            stack.append((y - 1, x))
        if y < h - 1:
            stack.append((y + 1, x))
        if x > 0:
            stack.append((y, x - 1))
        if x < w - 1:
            stack.append((y, x + 1))
    rgba[background, 3] = 0
    # orilla suave: píxeles casi blancos pegados al fondo pierden opacidad en proporción
    near = (~background) & (rgb.min(axis=-1) >= 225) & (rgba[..., 3] > 0)
    neighbor_bg = np.zeros_like(background)
    neighbor_bg[1:, :] |= background[:-1, :]
    neighbor_bg[:-1, :] |= background[1:, :]
    neighbor_bg[:, 1:] |= background[:, :-1]
    neighbor_bg[:, :-1] |= background[:, 1:]
    edge = near & neighbor_bg
    alpha = ((255 - rgb.min(axis=-1)) / (255 - 225) * 255).clip(0, 255).astype(np.uint8)
    rgba[edge, 3] = alpha[edge]
    return Image.fromarray(rgba, "RGBA")


def crop_to_content(img: Image.Image) -> Image.Image:
    bbox = img.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    return img.crop(bbox) if bbox else img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name in LOGOS:
        src = RAW / name
        img = crop_to_content(transparent_background(Image.open(src)))
        scale = HEIGHT / img.height
        img = img.resize((max(1, round(img.width * scale)), HEIGHT), Image.Resampling.LANCZOS)
        img.save(OUT / name, format="PNG", optimize=True)
        print(f"→ {(OUT / name).relative_to(ROOT)} {img.size} desde {src.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
