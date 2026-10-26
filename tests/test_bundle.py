"""F6: paquete de modelo (exportación, manifiesto, preprocesamiento desde JSON, paridad ONNX
con el paquete de prueba, CAM de la API ≡ CAM de melanoma.explain). Todo con pesos aleatorios;
lo que necesita el checkpoint real está en ``@pytest.mark.local``."""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image
from services.api.bundle import BundleError, load_bundle, verify_manifest
from services.api.cam import cam_from_features as api_cam
from services.api.cam import upsample as api_upsample
from services.api.inference import Predictor
from services.api.preprocess import Preprocessor, resize_smallest_side

from melanoma.data.resize import resize_one
from melanoma.data.transforms import build_transforms
from melanoma.explain import cam_from_features as ref_cam
from melanoma.explain import upsample as ref_upsample
from melanoma.explain.features import crop_transform
from melanoma.models import build_model

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def test_bundle(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Paquete de prueba (pesos aleatorios, semilla 0) construido una vez por sesión."""
    from scripts.make_test_bundle import build

    out = tmp_path_factory.mktemp("bundle")
    build(out, seed=0)
    return out


@pytest.fixture(scope="session")
def negative_bundle(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Pesos de la capa lineal en cero y sesgo −50: logit muy negativo y CAM nulo (con pesos
    negativos no basta: las activaciones tras SiLU pueden ser negativas y ReLU(w·A) > 0)."""
    from scripts.make_test_bundle import build

    out = tmp_path_factory.mktemp("bundle_neg")
    build(out, seed=0, negative_bias=-50.0, zero_weights=True)
    return out


@pytest.fixture(scope="session")
def ensemble_bundle(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Paquete de prueba con ensamble de tres (F6b): semillas 0, 1 y 2."""
    from scripts.make_test_bundle import build

    out = tmp_path_factory.mktemp("bundle_ens")
    build(out, seed=0, members=3)
    return out


@pytest.fixture(scope="session")
def negative_ensemble_bundle(tmp_path_factory: pytest.TempPathFactory) -> Path:
    from scripts.make_test_bundle import build

    out = tmp_path_factory.mktemp("bundle_ens_neg")
    build(out, seed=0, negative_bias=-50.0, zero_weights=True, members=3)
    return out


def synthetic_rgb(h: int = 512, w: int = 768, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    img = np.full((h, w, 3), (210, 165, 150), dtype=np.float32)
    ys, xs = np.mgrid[0:h, 0:w]
    disc = (ys - h / 2) ** 2 + (xs - w / 2) ** 2 < (0.2 * min(h, w)) ** 2
    img[disc] = (95, 55, 45)
    img += rng.normal(0, 6, img.shape)
    return np.clip(np.rint(img), 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- manifiesto


def test_bundle_has_seven_files(test_bundle: Path) -> None:
    names = {p.name for p in test_bundle.iterdir()}
    assert names == {
        "model.onnx",
        "preprocess.json",
        "calibration.json",
        "thresholds.json",
        "cam_weights.npy",
        "metrics.json",
        "manifest.json",
    }
    manifest = json.loads((test_bundle / "manifest.json").read_text())
    assert manifest["onnx"]["opset"] == {"ai.onnx": 17}
    assert manifest["onnx"]["outputs"] == ["logit", "features"]
    assert manifest["onnx"]["features_shape"] == [1280, 7, 7]
    assert manifest["kind"] == "test"


def test_bundle_manifest_sha256(test_bundle: Path, tmp_path: Path) -> None:
    """Cada archivo coincide con su SHA; un byte cambiado → no arranca."""
    verify_manifest(test_bundle)
    import shutil

    broken = tmp_path / "broken"
    shutil.copytree(test_bundle, broken)
    path = broken / "thresholds.json"
    data = bytearray(path.read_bytes())
    data[-2] ^= 0x01
    path.write_bytes(bytes(data))
    with pytest.raises(BundleError, match="SHA256"):
        load_bundle(broken)
    incomplete = tmp_path / "incomplete"
    shutil.copytree(test_bundle, incomplete)
    (incomplete / "cam_weights.npy").unlink()
    with pytest.raises(BundleError, match="falta"):
        load_bundle(incomplete)


def test_bundle_requires_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MODEL_BUNDLE_DIR", raising=False)
    with pytest.raises(BundleError, match="MODEL_BUNDLE_DIR"):
        load_bundle()


# ---------------------------------------------------------------- preprocesamiento


def test_preprocess_from_json_only(test_bundle: Path) -> None:
    """Cambiar ``mean`` en preprocess.json cambia la salida; no hay constantes en services/api."""
    spec = json.loads((test_bundle / "preprocess.json").read_text())
    img = synthetic_rgb()
    crop, x = Preprocessor(spec)(img)
    assert crop.shape == (224, 224, 3) and crop.dtype == np.uint8
    assert x.shape == (1, 3, 224, 224) and x.dtype == np.float32
    altered = dict(spec, mean=[m + 0.1 for m in spec["mean"]])
    _, x2 = Preprocessor(altered)(img)
    assert not np.allclose(x, x2)
    expected = np.broadcast_to(0.1 / np.asarray(spec["std"])[None, :, None, None], x.shape)
    np.testing.assert_allclose(x - x2, expected, atol=1e-5)

    forbidden = re.compile(r"0\.485|0\.456|0\.406|0\.229|0\.224|0\.225|(?<![\d.])0\.\d{3}(?![\d])")
    offenders = []
    for path in sorted((ROOT / "services" / "api").rglob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if forbidden.search(code):
                offenders.append(f"{path.name}:{lineno}: {line.strip()}")
    assert not offenders, "constantes de preprocesamiento en services/api:\n" + "\n".join(offenders)


def test_preprocess_matches_training_transform(test_bundle: Path) -> None:
    """La etapa 2 de la API reproduce SmallestMaxSize + CenterCrop + Normalize de
    albumentations exactamente (misma cv2.resize)."""
    spec = json.loads((test_bundle / "preprocess.json").read_text())
    _, data_config = build_model(
        "tf_efficientnetv2_s.in21k_ft_in1k", pretrained=False, num_classes=1, dropout=0.2
    )
    tf = build_transforms(data_config, 224, None, train=False, val_resize="center_crop")
    crop_tf = crop_transform(data_config, 224, "center_crop")
    for seed, (h, w) in enumerate(((512, 768), (768, 512), (300, 300), (341, 512))):
        img = synthetic_rgb(h, w, seed)
        crop, x = Preprocessor(spec)(img)
        assert np.array_equal(crop, crop_tf(image=img)["image"]), (h, w)
        np.testing.assert_allclose(x, tf(image=img)["image"].numpy()[None], atol=1e-6)


def test_stage1_matches_f1_resize(test_bundle: Path, tmp_path: Path) -> None:
    """La etapa 1 en memoria reproduce resize_one de F1 (draft + Lanczos a 512 + JPEG 95)
    bit a bit sobre un JPEG grande, y no toca una imagen con lado largo ≤ 512."""
    spec = json.loads((test_bundle / "preprocess.json").read_text())
    s1 = spec["stage1"]
    assert s1 == {
        "long_side": 512,
        "filter": "lanczos",
        "jpeg_quality": 95,
        "draft": True,
        "noop_if_long_side_leq": 512,
        "source": s1["source"],
    }
    pre = Preprocessor(spec)
    big = tmp_path / "big.jpg"
    Image.fromarray(synthetic_rgb(2000, 3000, seed=3)).save(big, format="JPEG", quality=90)
    ref_path = tmp_path / "ref.jpg"
    resize_one(big, ref_path, s1["long_side"], s1["jpeg_quality"])
    with Image.open(ref_path) as ref:
        ref_rgb = np.asarray(ref.convert("RGB"))
    with Image.open(big) as img:
        api_rgb = pre.stage1(img)
    assert api_rgb.shape == (341, 512, 3)
    assert np.array_equal(api_rgb, ref_rgb)
    # cadena completa desde bytes vs cadena de entrenamiento sobre el archivo de F1
    predictor = Predictor(load_bundle(test_bundle), 2)
    pred = predictor.predict_bytes(big.read_bytes())
    ref_pred = predictor.predict_array(ref_rgb)
    assert pred.logit == pytest.approx(ref_pred.logit, abs=1e-6)
    # ≤ 512: la etapa 1 no hace nada (ni recomprime)
    small = synthetic_rgb(341, 512, seed=4)
    small_path = tmp_path / "small.png"
    Image.fromarray(small).save(small_path)
    with Image.open(small_path) as img:
        assert np.array_equal(pre.stage1(img), small)


def test_resize_keeps_aspect_and_rounds_like_albumentations() -> None:
    import cv2

    img = np.zeros((300, 450, 3), dtype=np.uint8)
    out = resize_smallest_side(img, 224, cv2.INTER_CUBIC)
    assert out.shape == (224, 336, 3)
    same = resize_smallest_side(np.zeros((224, 224, 3), dtype=np.uint8), 224, cv2.INTER_CUBIC)
    assert same.shape == (224, 224, 3)


# ---------------------------------------------------------------- paridad y CAM


def test_onnx_parity_synthetic(test_bundle: Path) -> None:
    """Paquete de prueba: ONNX vs torch con los mismos pesos, ``|Δ| < 1e-4`` relativo.

    Con pesos aleatorios (BatchNorm sin estadísticas aprendidas) los logits llegan a
    cientos y las activaciones a miles; la tolerancia absoluta de 1e-4 de la spec está por
    debajo de la resolución de float32 a esa escala, así que se aplica relativa a
    ``max(1, |valor|)``. Con el checkpoint real (F6.2) la diferencia absoluta es 2e-5.
    """
    from scripts.make_test_bundle import BACKBONE

    torch.manual_seed(0)
    model, _ = build_model(BACKBONE, pretrained=False, num_classes=1, dropout=0.2)
    model.eval()
    bundle = load_bundle(test_bundle)
    predictor = Predictor(bundle, intra_op_threads=2)
    pre = Preprocessor(bundle.preprocess)
    x = torch.tensor(np.concatenate([pre(synthetic_rgb(seed=s))[1] for s in range(3)]))
    with torch.no_grad():
        feats = model.backbone.forward_features(x)
        logit = model.head(feats.mean(dim=(2, 3)))
    o_logit, o_feats = predictor.session.run(
        predictor.output_names, {predictor.input_name: x.numpy()}
    )
    rel_logit = np.abs(o_logit - logit.numpy()) / np.maximum(1.0, np.abs(logit.numpy()))
    rel_feats = np.abs(o_feats - feats.numpy()) / np.maximum(1.0, np.abs(feats.numpy()))
    assert rel_logit.max() < 1e-4, rel_logit.max()
    assert rel_feats.max() < 1e-3, rel_feats.max()
    np.testing.assert_allclose(
        bundle.cam_weights, model.head.fc.weight.detach().numpy().reshape(-1)
    )


def test_api_cam_equals_explain_cam() -> None:
    rng = np.random.default_rng(4)
    feats = rng.normal(size=(1280, 7, 7)).astype(np.float32)
    w = rng.normal(size=1280).astype(np.float32)
    np.testing.assert_allclose(api_cam(feats, w), ref_cam(feats, w), atol=1e-6)
    cam = api_cam(feats, w)
    np.testing.assert_allclose(api_upsample(cam, 224), ref_upsample(cam, 224), atol=1e-6)
    zero = api_cam(np.ones((4, 7, 7), np.float32), -np.ones(4, np.float32))
    assert not zero.any()


def test_predictor_no_positive_evidence(negative_bundle: Path) -> None:
    pred = Predictor(load_bundle(negative_bundle), 2).predict_array(synthetic_rgb())
    assert pred.cam_status == "no_positive_evidence"
    assert not pred.cam_grid.any()
    assert pred.probability < 1e-6 and not pred.refer


def test_predictor_rejects_bad_bytes(test_bundle: Path, tmp_path: Path) -> None:
    from services.api.inference import InputError

    predictor = Predictor(load_bundle(test_bundle), 2)
    with pytest.raises(InputError) as e:
        predictor.predict_bytes(b"no soy una imagen")
    assert e.value.status == 422
    small = tmp_path / "small.png"
    Image.fromarray(synthetic_rgb(32, 32)).save(small)
    with pytest.raises(InputError) as e:
        predictor.predict_bytes(small.read_bytes())
    assert e.value.status == 422
    gif = tmp_path / "x.gif"
    Image.fromarray(synthetic_rgb(128, 128)).save(gif)
    with pytest.raises(InputError) as e:
        predictor.predict_bytes(gif.read_bytes())
    assert e.value.status == 415


# ---------------------------------------------------------------- checkpoint real


@pytest.mark.local
def test_real_bundle_matches_checkpoint_and_parity() -> None:
    """Con el checkpoint real: el paquete existe, su manifiesto es válido y la paridad de
    F6.2 pasó en las cuatro comparaciones de tensores con decisiones idénticas."""
    bundle_dir = ROOT / "models" / "bundle_single"
    if not bundle_dir.exists():
        pytest.skip("models/bundle_single no existe (make export-bundle f6.mode=single)")
    bundle = load_bundle(bundle_dir)
    expected = json.loads((ROOT / "reports" / "f3_final_model.json").read_text())["sha256"]
    assert bundle.manifest["checkpoint"]["sha256"] == expected
    parity = json.loads((ROOT / "reports" / "f6_parity.json").read_text())
    assert parity["model_version"] == bundle.model_version
    for key in ("logit", "platt", "cam", "decision_tau95"):
        assert parity[key]["pass"], key
    assert parity["full_chain"]["decisions_identical"]


# ---------------------------------------------------------------- F6b: ensamble


def test_ensemble_bundle_manifest(ensemble_bundle: Path) -> None:
    """Tres ONNX y tres vectores de pesos nombrados por miembro, archivos JSON compartidos,
    `ensemble: logit_mean`, SHA256 de todo; un miembro alterado → no arranca."""
    manifest = json.loads((ensemble_bundle / "manifest.json").read_text())
    assert manifest["ensemble"]["method"] == "logit_mean" and manifest["ensemble"]["n_members"] == 3
    assert [m["run"] for m in manifest["members"]] == ["test-s0", "test-s1", "test-s2"]
    for m in manifest["members"]:
        assert (ensemble_bundle / m["onnx"]).exists() and (
            ensemble_bundle / m["cam_weights"]
        ).exists()
        assert manifest["files"][m["onnx"]] == m["onnx_sha256"]
        assert len(m["checkpoint"]["sha256"]) == 64
    assert manifest["onnx"]["features_shape"] == [1280, 7, 7]
    bundle = load_bundle(ensemble_bundle)
    assert bundle.n_members == 3 and bundle.ensemble == "logit_mean"
    with pytest.raises(BundleError, match="ensamble"):
        _ = bundle.onnx_path
    import shutil

    broken = tmp_dir = ensemble_bundle.parent / "broken_member"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    shutil.copytree(ensemble_bundle, broken)
    w = np.load(broken / "cam_weights_test-s1.npy")
    np.save(broken / "cam_weights_test-s1.npy", w * 2)
    with pytest.raises(BundleError, match="SHA256"):
        load_bundle(broken)


def test_parity_ensemble(ensemble_bundle: Path) -> None:
    """F6b.2 en sintético: la API promedia los LOGITS de los tres ONNX (no las probabilidades)
    y su CAM es la media de los mapas crudos w_i·A_i, luego ReLU y máximo; igual al cálculo
    con los mismos pesos en torch."""
    from scripts.make_test_bundle import random_model
    from services.api.cam import ensemble_cam

    bundle = load_bundle(ensemble_bundle)
    predictor = Predictor(bundle, intra_op_threads=2)
    pre = Preprocessor(bundle.preprocess)
    img = synthetic_rgb(seed=7)
    _, x = pre(img)
    xt = torch.tensor(x)
    feats_t, logits_t, weights = [], [], []
    for i in range(3):
        model, _ = random_model(i, None, False)
        with torch.no_grad():
            f = model.backbone.forward_features(xt)
            z = model.head(f.mean(dim=(2, 3)))
        feats_t.append(f[0].numpy())
        logits_t.append(float(z[0, 0]))
        weights.append(model.head.fc.weight.detach().numpy().reshape(-1))
    pred = predictor.predict_array(img)
    scale = max(1.0, max(abs(v) for v in logits_t))
    assert len(pred.member_logits) == 3
    for got, ref in zip(pred.member_logits, logits_t, strict=True):
        assert abs(got - ref) / scale < 1e-4
    assert pred.logit == pytest.approx(float(np.mean(pred.member_logits)), abs=1e-9)
    # promedio de probabilidades ≠ promedio de logits (con logits distintos)
    probs = [predictor.calibrate(z) for z in pred.member_logits]
    if max(logits_t) - min(logits_t) > 1e-3:
        assert pred.probability != pytest.approx(float(np.mean(probs)), abs=1e-12)
    cam_ref = ensemble_cam(feats_t, weights)
    if cam_ref.max() > 0:
        assert np.corrcoef(cam_ref.ravel(), pred.cam_grid.ravel())[0, 1] > 0.999
    assert pred.cam_grid.shape == (7, 7)
    # Linealidad: media de mapas crudos == mapa crudo del "modelo promedio" en cada celda
    from services.api.cam import raw_cam

    raws = np.mean([raw_cam(f, w) for f, w in zip(feats_t, weights, strict=True)], axis=0)
    assert raws.shape == (7, 7)


def test_bundle_matches_protocol() -> None:
    """El exportador compara el paquete con el protocolo valor por valor (F6b.1)."""
    from melanoma.export.bundle import protocol_mismatches

    shas = [f"{i:064x}" for i in range(3)]
    manifest = {
        "ensemble": {"method": "logit_mean"},
        "members": [
            {"run": f"a1-s{i}", "checkpoint": {"file": f"a1-s{i}.ckpt", "sha256": s}}
            for i, s in enumerate(shas)
        ],
    }
    calibration = {"a": 0.5, "b": -3.0}
    thresholds = {"tau_95": {"tau": 0.004}, "tau_90": {"tau": 0.006}}
    protocol = {
        "models": [{"file": f"a1-s{i}.ckpt", "sha256": s} for i, s in enumerate(shas)],
        "ensemble": "logit_mean",
        "tta": ["identity"],
        "stacker": None,
        "calibration": {"a": 0.5, "b": -3.0},
        "thresholds": {"tau_95": 0.004, "tau_90": 0.006},
    }
    assert protocol_mismatches(manifest, calibration, thresholds, protocol) == []
    bad = json.loads(json.dumps(protocol))
    bad["calibration"]["a"] = 0.51
    bad["thresholds"]["tau_90"] = 0.0061
    bad["tta"] = ["identity", "hflip"]
    bad["models"][2]["sha256"] = "f" * 64
    found = protocol_mismatches(manifest, calibration, thresholds, bad)
    assert (
        len(found) == 4 and any("Platt a" in f for f in found) and any("tau_90" in f for f in found)
    )


@pytest.mark.local
def test_real_ensemble_bundle_matches_protocol_and_parity() -> None:
    """Con los checkpoints reales: models/bundle es el ensamble del protocolo de F4b y la
    paridad de F6b.2 pasó, incluida la comparación con el caché de logits de F3b."""
    from omegaconf import OmegaConf

    from melanoma.export.bundle import protocol_mismatches

    bundle_dir = ROOT / "models" / "bundle"
    if not bundle_dir.exists():
        pytest.skip("models/bundle no existe (make export-bundle)")
    bundle = load_bundle(bundle_dir)
    protocol = OmegaConf.to_container(OmegaConf.load(ROOT / "docs" / "f4b_protocol.yaml"))
    assert (
        protocol_mismatches(bundle.manifest, bundle.calibration, bundle.thresholds, protocol) == []
    )
    parity = json.loads((ROOT / "reports" / "f6b_parity.json").read_text())
    assert parity["model_version"] == bundle.model_version and parity["all_pass"]
    assert parity["vs_val_logits_cache"]["pass"]
