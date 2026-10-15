"""Falla con código 1 si una imagen Docker supera el límite en MB.

Mide el tamaño **sin comprimir**: la suma de las capas de ``docker history``. No se usa
``docker image inspect .Size`` porque con el almacén de containerd (Docker 29 en WSL) devuelve
el tamaño comprimido y con el clásico (runners de GitHub) el descomprimido: local y CI no
coincidían.

Uso: ``python scripts/check_image_size.py <imagen> <max_mb>``.
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    image, max_mb = sys.argv[1], float(sys.argv[2])
    layers = subprocess.run(
        ["docker", "history", "--human=false", "--format", "{{.Size}}", image],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    size_mb = sum(int(s) for s in layers) / (1024 * 1024)
    print(f"{image}: {size_mb:.1f} MB sin comprimir (límite {max_mb:.0f} MB)")
    if size_mb > max_mb:
        print("ERROR: la imagen supera el límite. ¿Se coló torch/timm/lightning en `api`?")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
