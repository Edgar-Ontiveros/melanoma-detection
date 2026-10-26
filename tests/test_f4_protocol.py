"""Guardarraíles de F4: el protocolo debe estar commiteado, la bitácora se escribe antes de
leer el split de prueba, y DDI nunca se acerca a Kaggle."""

from __future__ import annotations

import importlib.util
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "evaluate_test", ROOT / "scripts/evaluate_test.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_protocol_committed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    et = _load()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "f4_protocol.yaml").write_text("a: 1\n")

    def fake(cmd, text=True):
        if "ls-files" in cmd:
            return "docs/f4_protocol.yaml\n"
        if "status" in cmd:
            return fake.dirty
        raise AssertionError(cmd)

    fake.dirty = " M docs/f4_protocol.yaml\n"
    monkeypatch.setattr(et.subprocess, "check_output", fake)
    with pytest.raises(SystemExit, match="sin commitear"):
        et.ensure_protocol_committed(tmp_path)
    fake.dirty = ""
    assert len(et.ensure_protocol_committed(tmp_path)) == 64
    monkeypatch.setattr(et.subprocess, "check_output", lambda cmd, text=True: "")
    with pytest.raises(SystemExit, match="no está en git"):
        et.ensure_protocol_committed(tmp_path)


def test_protocol_is_committed_in_this_repo() -> None:
    """El protocolo real está versionado y su commit precede al del script de evaluación."""

    def first(path: str) -> list[str]:
        out = subprocess.check_output(
            ["git", "-C", str(ROOT), "log", "--diff-filter=A", "--format=%ct", "--", path],
            text=True,
        )
        return out.strip().splitlines()

    protocol, script = first("docs/f4_protocol.yaml"), first("scripts/evaluate_test.py")
    assert protocol, "docs/f4_protocol.yaml no está en git"
    if script:  # el script puede no estar commiteado aún en el árbol de trabajo
        assert int(protocol[-1]) <= int(script[-1]), (
            "el protocolo debe commitearse antes que el script"
        )


def test_access_logged_before_read(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Con el sistema de archivos simulado: la bitácora se escribe antes de abrir test.txt."""
    et = _load()
    events: list[str] = []

    class Stop(Exception):
        pass

    monkeypatch.setattr(et, "ensure_protocol_committed", lambda root, protocol=None: "p" * 64)
    monkeypatch.setattr(et, "verify_checkpoint", lambda root, pc: ["c" * 64])
    monkeypatch.setattr(et, "append_access_log", lambda *a, **k: events.append("log") or "line")
    monkeypatch.setattr(et, "verify_split_hashes", lambda d: {})

    def fake_read(splits_dir):
        events.append("read")
        raise Stop

    monkeypatch.setattr(et, "read_test_ids", fake_read)
    from types import SimpleNamespace

    cfg = SimpleNamespace(
        f4=SimpleNamespace(protocol="docs/f4_protocol.yaml", access_log="logs/x.log"),
        data={
            "env": "local",
            "paths": {"local": {"images_dir": "i", "manifest_path": "m", "splits_dir": "s"}},
        },
    )
    monkeypatch.setattr(et.OmegaConf, "load", lambda p: SimpleNamespace(model=SimpleNamespace()))
    with pytest.raises(Stop):
        et.run(cfg, tmp_path, "prueba")
    assert events == ["log", "read"], events


def _fake_cfg():
    from types import SimpleNamespace

    return SimpleNamespace(
        f4=SimpleNamespace(protocol="docs/f4_protocol.yaml", access_log="logs/x.log"),
        data={
            "env": "local",
            "paths": {"local": {"images_dir": "i", "manifest_path": "m", "splits_dir": "s"}},
        },
    )


def test_second_access_is_last(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Bitácora simulada con dos líneas → el script aborta antes de registrar o leer nada."""
    et = _load()
    events: list[str] = []
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "x.log").write_text("1\tprimero\n2\tsegundo\n", encoding="utf-8")
    monkeypatch.setattr(
        et,
        "ensure_protocol_committed",
        lambda root, protocol=None: events.append("protocol") or "p" * 64,
    )
    monkeypatch.setattr(
        et, "verify_checkpoint", lambda root, pc: events.append("ckpt") or ["c" * 64]
    )
    monkeypatch.setattr(et, "append_access_log", lambda *a, **k: events.append("log") or "line")
    monkeypatch.setattr(et, "read_test_ids", lambda d: events.append("read") or [])
    from types import SimpleNamespace

    monkeypatch.setattr(et.OmegaConf, "load", lambda p: SimpleNamespace(model=SimpleNamespace()))
    with pytest.raises(SystemExit, match="No hay tercer acceso"):
        et.run(_fake_cfg(), tmp_path, "tercero")
    assert events == [], events
    # Con una línea y un protocolo que declara el acceso 2, pasa el paso 0.
    (tmp_path / "logs" / "x.log").write_text("1\tprimero\n", encoding="utf-8")
    assert et.ensure_access_budget(tmp_path, "logs/x.log", SimpleNamespace(access_number=2)) == 1
    with pytest.raises(SystemExit, match="acceso número 1"):
        et.ensure_access_budget(tmp_path, "logs/x.log", SimpleNamespace(access_number=1))


def test_f4b_protocol_committed_before_second_access() -> None:
    """Si la bitácora ya registra el segundo acceso, docs/f4b_protocol.yaml estaba en git antes
    de esa línea (spec F3b-F4b, criterio 6). El código de evaluate_test.py se commitea antes del
    protocolo (decisión del 2026-10-22); lo que espera al protocolo es la ejecución."""
    from datetime import datetime

    log = ROOT / "logs" / "test_set_access.log"
    lines = [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) <= 2, "la bitácora no puede tener más de dos accesos"
    if len(lines) < 2:
        pytest.skip("el segundo acceso no se ha ejecutado")
    import hashlib

    def git(*args: str) -> str:
        return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()

    # 1. El protocolo con el que se ejecutó (SHA256 en la bitácora) es el que está commiteado.
    fields = dict(f.split("=", 1) for f in lines[1].split("\t")[1:] if "=" in f)
    committed = hashlib.sha256(
        subprocess.check_output(["git", "-C", str(ROOT), "show", "HEAD:docs/f4b_protocol.yaml"])
    ).hexdigest()
    assert fields["protocol_sha256"] == committed, (
        "la bitácora registra un protocolo distinto del commiteado"
    )
    # 2. El commit que añadió el protocolo precede a la segunda línea. Solo con historial
    #    completo: en un clon superficial (fetch-depth 1) git atribuye el archivo al único commit.
    if git("rev-parse", "--is-shallow-repository") == "true":
        pytest.skip("clon superficial: no hay historial para fechar el commit del protocolo")
    out = git("log", "--diff-filter=A", "--format=%ct", "--", "docs/f4b_protocol.yaml").splitlines()
    assert out, "docs/f4b_protocol.yaml no está en git"
    second = datetime.fromisoformat(lines[1].split("\t")[0]).timestamp()
    assert int(out[-1]) <= second, "el protocolo de F4b debe commitearse antes del segundo acceso"


def test_only_evaluate_test_reads_the_split_in_the_script() -> None:
    src = (ROOT / "scripts/evaluate_test.py").read_text(encoding="utf-8")
    assert src.index("append_access_log(root") < src.index("read_test_ids(paths"), (
        "el registro debe ir antes de la lectura"
    )


def test_ddi_never_uploaded() -> None:
    """Ningún script ni notebook mezcla rutas de DDI con llamadas a Kaggle."""
    ddi = re.compile(r"raw/ddi|ddi_metadata|DDI", re.I)
    kaggle = re.compile(r"kaggle|KaggleApi|kernels push|datasets create", re.I)
    offenders = []
    for path in sorted(
        list((ROOT / "scripts").glob("*.py")) + list((ROOT / "notebooks").glob("*.ipynb"))
    ):
        text = path.read_text(encoding="utf-8")
        if ddi.search(text) and kaggle.search(text):
            offenders.append(path.name)
    assert not offenders, f"DDI junto a Kaggle en: {offenders}"
