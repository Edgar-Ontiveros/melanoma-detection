"""F7: la interfaz. Sin constantes del modelo en el frontend, limitaciones presentes, ejemplos
de validación (nunca DDI), prefijo /api y SPA, y la imagen Docker con el build."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from services.api.main import build_app, count_sections

from tests.test_bundle import test_bundle  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "services" / "web"
LIMITATIONS = ROOT / "docs" / "f4_limitations.md"


def _web_sources() -> list[Path]:
    return [
        p
        for p in sorted((WEB / "src").rglob("*"))
        if p.is_file() and p.suffix in (".ts", ".tsx", ".js", ".json") and ".test." not in p.name
    ]


def test_web_no_model_constants() -> None:
    """Ningún número de umbral, prevalencia o métrica en services/web/src (fuera de pruebas y
    CSS): ni los literales conocidos ni flotantes con tres o más decimales."""
    known = re.compile(r"0\.0039|0\.965|0\.428|0\.834|0\.0164|0\.096")
    floats = re.compile(r"(?<![\w.])\d+\.\d{3,}(?![\w.])")
    offenders = []
    for path in _web_sources():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("//", 1)[0]
            if known.search(code) or floats.search(code):
                offenders.append(f"{path.relative_to(ROOT)}:{lineno}: {line.strip()}")
    assert not offenders, "constantes del modelo en el frontend:\n" + "\n".join(offenders)


def test_limitations_present() -> None:
    """docs/f4_limitations.md existe y tiene al menos 8 secciones o párrafos. La interfaz no
    se cierra sin las limitaciones; las escribe el autor (F4, sección 10)."""
    assert LIMITATIONS.exists(), (
        "falta docs/f4_limitations.md: la ficha del modelo muestra «pendiente» hasta que exista"
    )
    text = LIMITATIONS.read_text(encoding="utf-8")
    assert count_sections(text) >= 8, f"solo {count_sections(text)} bloques en f4_limitations.md"


def test_example_images_are_val_not_ddi() -> None:
    examples = json.loads((WEB / "public" / "examples" / "examples.json").read_text())
    ids = {e["image_id"] for e in examples["items"]}
    assert len(ids) == 4
    val = set((ROOT / "data" / "splits" / "val.txt").read_text().split())
    assert ids <= val, ids - val
    truths = [e["truth"] for e in examples["items"]]
    assert truths.count("melanoma") == 2 and truths.count("benigna") == 2
    for e in examples["items"]:
        assert (WEB / "public" / e["file"]).exists(), e["file"]
    ddi = re.compile(r"raw/ddi|ddi_metadata|\bDDI\b(?!, Stanford\)|\)| \(Stanford)")
    offenders = []
    for path in sorted(WEB.rglob("*")):
        if path.is_file() and "node_modules" not in path.parts and "dist" not in path.parts:
            if path.suffix in (".ts", ".tsx", ".json", ".html", ".css", ".md"):
                text = path.read_text(encoding="utf-8")
                if re.search(r"raw/ddi|ddi_metadata|ddi/images", text, re.I):
                    offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, f"rutas de DDI en services/web: {offenders}"
    assert not ddi.search("")  # el patrón compila


@pytest.fixture()
def spa_client(test_bundle: Path, tmp_path: Path):  # noqa: F811
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(
        "<!doctype html><html><body><div id='root'>SPA</div></body></html>"
    )
    (dist / "assets" / "app.js").write_text("console.log('ok')")
    lim = tmp_path / "f4_limitations.md"
    lim.write_text("# Limitaciones\n\n" + "\n\n".join(f"Párrafo {i}." for i in range(8)))
    with TestClient(
        build_app(test_bundle, intra_op_threads=2, web_dist=dist, limitations_md=lim)
    ) as c:
        yield c


# ---------------------------------------------------------------- F7b: sistema visual

DIST = WEB / "dist"
TOKENS = WEB / "src" / "styles" / "tokens.css"


def _dist_or_skip() -> Path:
    if not (DIST / "index.html").exists():
        pytest.skip("services/web/dist no existe (make web-build)")
    return DIST


def test_web_no_external_requests() -> None:
    """El build no pide nada a terceros: sin fuentes de Google, sin <link>/<script> externos,
    sin @import ni url(https://…) en el CSS; la fuente va dentro de dist. Los href de enlaces
    del contenido (repositorio, DOI, DDI, UACH) sí se permiten."""
    dist = _dist_or_skip()
    html = (dist / "index.html").read_text(encoding="utf-8")
    assert "fonts.googleapis" not in html and "gstatic" not in html
    for tag, attr in (("link", "href"), ("script", "src")):
        for m in re.finditer(rf"<{tag}\b[^>]*\b{attr}=\"([^\"]+)\"", html):
            assert not re.match(r"https?://|//", m.group(1)), f"{tag} externo: {m.group(1)}"
    for css in dist.glob("assets/*.css"):
        text = css.read_text(encoding="utf-8")
        assert "@import" not in text, css.name
        assert not re.search(r"url\(\s*[\"']?(https?:)?//", text), f"url externa en {css.name}"
        assert "/fonts/InterVariable-latin.woff2" in text, "la fuente no se referencia desde el CSS"
    for js in dist.glob("assets/*.js"):
        text = js.read_text(encoding="utf-8")
        assert "fonts.googleapis" not in text and "gstatic.com" not in text
    assert (dist / "fonts" / "InterVariable-latin.woff2").exists()
    assert (dist / "fonts" / "LICENSE-Inter.txt").exists()


def test_web_icons_present() -> None:
    """mark.svg, favicon.svg, favicon.ico y apple-touch-icon.png existen en dist y los tres
    últimos están referenciados en index.html; el título es el del sistema."""
    dist = _dist_or_skip()
    for name in (
        "mark.svg",
        "favicon.svg",
        "favicon.ico",
        "apple-touch-icon.png",
        "escudo-uach.png",
        "facultad-ingenieria.png",
        "eo.svg",
    ):
        assert (dist / name).exists(), name
    html = (dist / "index.html").read_text(encoding="utf-8")
    assert 'href="/favicon.svg"' in html and 'href="/favicon.ico"' in html
    assert 'rel="apple-touch-icon" href="/apple-touch-icon.png"' in html
    assert "<title>Detección asistida de melanoma</title>" in html
    assert 'name="theme-color" content="#0B6E99"' in html
    svg = (dist / "favicon.svg").read_text(encoding="utf-8")
    assert 'r="11' in svg and 'r="4' in svg and "prefers-color-scheme: dark" in svg


def test_web_tokens_only() -> None:
    """Ningún color hexadecimal ni rgb() en el CSS de componentes fuera de tokens.css."""
    pattern = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\(")
    offenders = []
    for path in sorted((WEB / "src").rglob("*.css")):
        if path == TOKENS:
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{lineno}: {line.strip()}")
    assert not offenders, "colores fuera de tokens.css:\n" + "\n".join(offenders)
    tokens = TOKENS.read_text(encoding="utf-8")
    for name, value in (
        ("--bg", "#ffffff"),
        ("--surface", "#f8fafc"),
        ("--border", "#e2e8f0"),
        ("--border-strong", "#cbd5e1"),
        ("--text", "#0f172a"),
        ("--text-2", "#475569"),
        ("--accent", "#0b6e99"),
        ("--accent-hover", "#085578"),
        ("--accent-bright", "#0a93c6"),
        ("--accent-tint", "#e8f4fa"),
        ("--accent-tint-border", "#b8dcee"),
        ("--signature", "#7a2a8a"),
    ):
        assert f"{name}: {value};" in tokens, name


def test_api_prefix_and_spa(spa_client: TestClient) -> None:
    assert spa_client.get("/api/health").status_code == 200
    assert spa_client.get("/api/model-info").json()["model_version"]
    r = spa_client.get("/")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert "SPA" in r.text
    assert spa_client.get("/modelo").status_code == 200 and "SPA" in spa_client.get("/modelo").text
    assert spa_client.get("/assets/app.js").status_code == 200
    assert "SPA" in spa_client.get("/../../etc/passwd").text  # nunca sale de dist
    lim = spa_client.get("/api/limitations").json()
    assert lim["n_sections"] == 9 and lim["markdown"].startswith("# Limitaciones")
    assert spa_client.get("/health").status_code == 200  # cae en la SPA: sin API fuera de /api


def test_limitations_404_when_missing(test_bundle: Path, tmp_path: Path) -> None:  # noqa: F811
    with TestClient(
        build_app(test_bundle, intra_op_threads=2, limitations_md=tmp_path / "no.md")
    ) as c:
        r = c.get("/api/limitations")
    assert r.status_code == 404 and "pendiente" in r.json()["detail"]


def test_web_build_in_docker(test_bundle: Path) -> None:  # noqa: F811
    """La imagen contiene el build y sirve / con 200 (y /api/health). Construye la imagen si
    Docker está disponible; si no, se salta."""
    if shutil.which("docker") is None:
        pytest.skip("docker no disponible")
    if subprocess.run(["docker", "info"], capture_output=True).returncode != 0:
        pytest.skip("el demonio de docker no responde")
    build = subprocess.run(
        ["docker", "build", "-q", "-f", "services/api/Dockerfile", "-t", "melanoma-api", "."],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr[-2000:]
    # El contenedor corre como usuario sin privilegios y el tmp de pytest es 700: copia legible.
    readable = Path(tempfile.mkdtemp(prefix="melanoma-bundle-"))
    shutil.copytree(test_bundle, readable / "bundle")
    for path in [readable, *readable.rglob("*")]:
        path.chmod(0o755 if path.is_dir() else 0o644)
    name = f"melanoma-api-test-{int(time.time())}"
    run = subprocess.run(
        [
            "docker", "run", "-d", "--name", name, "-p", "127.0.0.1:0:8000",
            "-v", f"{readable / 'bundle'}:/bundle:ro", "melanoma-api",
        ],
        capture_output=True,
        text=True,
    )  # fmt: skip
    assert run.returncode == 0, run.stderr
    try:
        port = subprocess.check_output(["docker", "port", name, "8000/tcp"], text=True).strip()
        port = port.splitlines()[0].rsplit(":", 1)[1]
        base = f"http://127.0.0.1:{port}"
        for _ in range(60):
            try:
                if urllib.request.urlopen(f"{base}/api/health", timeout=2).status == 200:
                    break
            except Exception:  # noqa: BLE001
                time.sleep(1)
        else:
            logs = subprocess.run(["docker", "logs", name], capture_output=True, text=True)
            pytest.fail(f"la API no levantó en el contenedor:\n{logs.stdout}\n{logs.stderr}")
        with urllib.request.urlopen(f"{base}/", timeout=5) as r:
            assert r.status == 200
            html = r.read().decode()
        assert '<div id="root">' in html and "/assets/" in html
        with urllib.request.urlopen(f"{base}/modelo", timeout=5) as r:
            assert r.status == 200
        with urllib.request.urlopen(f"{base}/examples/examples.json", timeout=5) as r:
            assert len(json.load(r)["items"]) == 4
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        shutil.rmtree(readable, ignore_errors=True)
