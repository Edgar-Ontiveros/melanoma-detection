# F6b — Paquete con ensamble

Especificación de la fase. Depende de F4b (criterio de despliegue cumplido: se despliega E1/none). Bloquea F7b y F8.

## Objetivo
El paquete de modelo y la API sirven el ensamble E1/none exactamente como quedó en `docs/f4b_protocol.yaml` (A1 semillas 0, 1 y 2; promedio de logits; sin TTA; sin apilador; Platt a = 0.4473, b = −3.3553; τ95 = 0.003851, τ90 = 0.005600), con la paridad y los guardarraíles de F6. El paquete del modelo único (F4) se conserva como release anterior; no se borra.

## F6b.1 — Exportación
- Tres ONNX opset 17, uno por checkpoint, con las dos salidas de F6 (logit y features 1280×7×7) y los pesos de la cabeza (w, b) de cada modelo para el CAM.
- `manifest.json`: miembros (archivo, SHA256 del ONNX, SHA256 del checkpoint de origen), `ensemble: logit_mean`, calibración, umbrales y tasa base copiados del protocolo. El exportador compara cada valor con `docs/f4b_protocol.yaml` y falla si algo difiere.
- Nombre `model-<git>-<sha8>` como en F6. Tamaño del paquete en el reporte.

## F6b.2 — Paridad (solo validación; nada toca el test)
- 200 imágenes de validación (las de F6): |media de logits ONNX − media de logits PyTorch| ≤ 1e-4 por imagen con el preprocesamiento de dos etapas; probabilidad calibrada ≤ 1e-6.
- Contra `reports/predictions/f3b_val_logits.npz` (vista identity), por miembro, con las imágenes de 512 px: ≤ 1e-3. Reportar el máximo observado.

## F6b.3 — API
- Carga los N modelos del manifiesto; un solo preprocesamiento; logit = media; probabilidad = Platt del protocolo.
- CAM del ensamble = media de los mapas crudos (w_i · features_i) antes de recortar y normalizar; después, la regla de F5 incluido `no_positive_evidence`. Por linealidad equivale al CAM del logit promedio.
- `/model-info`: `ensemble: {members: 3, method: "logit_mean"}`, versión, métricas del test de F4b con IC (AUC-ROC, AUPRC, sensibilidad, especificidad, VPP, VPN en τ95; fecha 2026-10-26) y un bloque `previous_model` con las del modelo único de F4 para la tabla lado a lado. `operating_point` con τ95 del protocolo F4b. El `disclaimer` no cambia.
- Latencia: bench de F6; objetivo p95 < 200 ms en la laptop; reportar p50/p95.

## F6b.4 — Docker
Límite de la imagen 650 MB sin comprimir, medido igual en local y CI; justificación en README (torch sigue sin caber). Reportar tamaño sin comprimir y comprimido.

## F6b.5 — Interfaz (mínimo; F7b hace el resto)
/modelo indica que el modelo es un ensamble de tres y muestra la tabla lado a lado desde `/model-info`. Los textos de la recomendación no cambian. `test_web_no_model_constants` sigue aplicando.

## F6b.6 — Release
Release de GitHub `model-<git>-<sha8>` con el paquete; el anterior se conserva. `docs/API.md` actualizado.

## Pruebas
`test_bundle_matches_protocol`, `test_parity_ensemble`, `test_api_ensemble` (3 miembros, CAM con la forma de F6, `no_positive_evidence` funciona), `test_model_info_ensemble`, `test_docker_size` (650). Las de F6 adaptadas a N modelos, en verde.

## Criterios de aceptación
1. Paquete con tres ONNX y manifiesto verificado contra el protocolo.
2. Paridad F6b.2 dentro de tolerancia.
3. API sirve el ensamble con CAM promediado.
4. `/model-info` con ensamble, métricas de F4b y modelo anterior.
5. p95 < 200 ms.
6. Imagen ≤ 650 MB sin comprimir.
7. Release publicado.
8. Pruebas, `make ci`, push; README y `docs/historial.md` al día.

Al cerrar F6b repórtame: paridad máxima, p50/p95, tamaño de la imagen, nombre del release.

---

## Estado y desviaciones respecto a la spec

Hecha el 2026-10-26 (commit del código `28a90b4`; reportes y release en el commit siguiente).

1. **F6b.1.** `make export-bundle` (`f6.mode=ensemble`, por defecto) produce `models/bundle/`
   con `model_a1-s{0,1,2}.onnx` (opset 17, dos salidas), `cam_weights_a1-s{0,1,2}.npy`,
   `preprocess.json` único, `calibration.json` y `thresholds.json` copiados de
   `docs/f4b_protocol.yaml`, `metrics.json` con el test de F4b (IC en τ95 por bootstrap desde
   `reports/predictions/f4b_test.csv`), `previous_model` (F4) y `base_rate`. El exportador
   compara miembros, SHA256, método, TTA, apilador, Platt y τ95/τ90 con el protocolo y se
   detiene si algo difiere (`protocol_mismatches`). Paquete `28a90b4-4264e888`, 241.8 MB;
   `sha8` = SHA256 de los SHA256 de los tres checkpoints. **Desviación menor:** el protocolo no
   trae tasa base; se toma la prevalencia observada en el test de F4b y se declara su origen.
2. **F6b.2.** `reports/f6b_parity.json`, `all_pass = true`: media de logits ONNX vs torch máx
   |Δ| 9.3e-6; Platt 6.9e-18; CAM promediado corr mín 0.99999999988 (un mapa nulo en ambos);
   decisiones idénticas; cadena completa desde bytes 1.0e-5 (p95 4.9e-6); 100 originales de
   640–6,000 px 8.3e-6; por miembro contra `f3b_val_logits.npz` (identity) **2.2e-5** máximo
   (a1-s0 1.6e-5, a1-s1 1.4e-5, a1-s2 2.2e-5).
3. **F6b.3.** `services/api` carga N sesiones de onnxruntime, un solo preprocesamiento,
   logit = media, Platt del protocolo; CAM = media de los mapas crudos `w_i·A_i` y después
   ReLU y máximo (`services/api/cam.py::ensemble_cam`), con `no_positive_evidence` intacto.
   `/model-info` trae `ensemble`, `previous_model`, `operating_point` y `tau_95.ci`.
   Latencia (`reports/f6b_latency.md`, en proceso, 4 hilos): **p50 98.6 ms, p95 118.3 ms**,
   p99 128.1; onnx p50 86 ms de los tres modelos. Cumple p95 < 200 ms.
4. **F6b.4.** Límite 650 MB sin comprimir en CI, Makefile y README (`test_docker_size`). La
   imagen no cambia por el paquete (se monta): **437.0 MB sin comprimir, 152.3 MB comprimida**.
5. **F6b.5.** `/modelo` indica que el modelo es un ensamble de tres redes y muestra la tabla
   lado a lado modelo único / ensamble desde `/model-info`; los textos de la recomendación no
   cambian; `test_web_no_model_constants` en verde.
6. **F6b.6.** Release `model-28a90b4-4264e888` con `melanoma-bundle-28a90b4-4264e888.tar.gz`
   y su `.sha256`; `model-c62a515-e0ecf981` (modelo único) se conserva. `docs/API.md` al día.
7. Pruebas nuevas: `test_ensemble_bundle_manifest`, `test_parity_ensemble`,
   `test_bundle_matches_protocol`, `test_api_ensemble`, `test_model_info_ensemble`,
   `test_docker_size` y `test_check_image_size_fails_above_limit`; las de F6 adaptadas
   (`bundle.members`, `predictor.sessions`; `model.onnx` sigue válido para un solo modelo).
   `make ci` en verde: 148 pruebas.

Criterios de aceptación: 8/8.
