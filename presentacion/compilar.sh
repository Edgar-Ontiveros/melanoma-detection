#!/bin/bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="texlive/texlive:latest-medium"
TEX="${1:-presentacion_tesis.tex}"

docker run --rm --network none \
  --user "$(id -u):$(id -g)" \
  -v "$DIR":/work -w /work \
  "$IMAGE" \
  sh -c "latexmk -pdf -interaction=nonstopmode -halt-on-error $TEX && latexmk -c $TEX"
