"""F6b.4: el límite de la imagen Docker (650 MB sin comprimir) es el mismo en CI, en el
Makefile y en el README, y `check_image_size.py` falla por encima de él."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIMIT_MB = 650


def _limits_in(text: str) -> set[int]:
    return {int(m) for m in re.findall(r"check_image_size\.py melanoma-api (\d+)", text)}


def test_docker_size() -> None:
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    make = (ROOT / "Makefile").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert _limits_in(ci) == {LIMIT_MB}, "ci.yml no usa el límite de F6b"
    assert _limits_in(make) == {LIMIT_MB}, "Makefile no usa el límite de F6b"
    assert f"{LIMIT_MB} MB" in readme, "el README no justifica el límite"
    assert f"máx. {LIMIT_MB} MB sin comprimir" in ci


def test_check_image_size_fails_above_limit(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    spec = importlib.util.spec_from_file_location("cis", ROOT / "scripts" / "check_image_size.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    class Out:
        def __init__(self, s: str) -> None:
            self.stdout = s

    layers_ok = " ".join(str(v) for v in (200 * 1024 * 1024, 300 * 1024 * 1024))
    layers_bad = " ".join(str(v) for v in (400 * 1024 * 1024, 300 * 1024 * 1024))
    monkeypatch.setattr(mod.sys, "argv", ["x", "melanoma-api", str(LIMIT_MB)])
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: Out(layers_ok))
    assert mod.main() == 0
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: Out(layers_bad))
    assert mod.main() == 1
    assert "supera" in capsys.readouterr().out
