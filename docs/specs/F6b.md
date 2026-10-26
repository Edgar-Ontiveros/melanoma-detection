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
