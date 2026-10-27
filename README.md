# Detección asistida de melanoma

Clasificador de lesiones cutáneas con redes convolucionales, desarrollado como proyecto de tesis.

## Qué es y qué no es

Esto es una **herramienta educativa de detección asistida de melanoma (apoyo a la priorización, no diagnóstico)**: un experimento de aprendizaje
automático sobre imágenes dermatoscópicas públicas, con explicabilidad y una API de
demostración.

**No es un dispositivo de diagnóstico.** No está validado clínicamente, no ha sido evaluado
por ninguna autoridad sanitaria y no debe usarse para tomar, confirmar o descartar decisiones
médicas. Cualquier salida del modelo es una probabilidad estadística sobre una imagen, no
una opinión médica. Ante una lesión sospechosa, consulte a un dermatólogo.

## Instalación

Plataforma de desarrollo soportada: **WSL2 con Ubuntu 24.04** (o Ubuntu nativo). Requiere
[uv](https://docs.astral.sh/uv/) y Python 3.12 (uv lo descarga si falta).

### Laptop / CPU (WSL/Ubuntu)

```bash
git clone https://github.com/Edgar-Ontiveros/melanoma-detection.git melanoma
cd melanoma
make setup        # uv sync --extra train --group dev  (ruedas CPU de PyTorch, del lockfile)
make ci           # lint + pruebas + humo, lo mismo que GitHub Actions
```

`make setup` instala los grupos `core`, `train` y `dev` con las ruedas **CPU** de PyTorch
fijadas en `uv.lock` (índice `https://download.pytorch.org/whl/cpu`).

### Instancia con GPU (entrenamiento)

```bash
make setup-gpu CUDA=cu126
```

Ejecuta `make setup` y después reinstala `torch` y `torchvision` desde
`https://download.pytorch.org/whl/cu126` (o el índice que indique `CUDA=`). El lockfile no
cambia: fijar CUDA en él rompería la instalación local. Verificar con:

```bash
uv run --no-sync python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

## Prueba de humo

```bash
make smoke        # o: uv run python scripts/smoke_train.py
```

Genera 50 JPEG sintéticos en `outputs/smoke/synthetic/` (manifiesto + `train.txt`/`val.txt`) y
entrena `resnet18` sin pesos preentrenados con el **DataModule real** (albumentations, sampler,
`pos_weight=auto`), 2 épocas a 224 px, batch 8, en CPU; después evalúa validación con bootstrap
por paciente y escribe los mismos artefactos que una corrida real. No descarga nada. Debe
terminar en menos de 2 minutos. Lee `configs/smoke.yaml` con Hydra, exactamente como lo haría
una corrida real, así que un error de configuración aparece aquí y no a los 40 minutos de GPU.

## Entrenamiento y evaluación (F2)

```bash
make baseline-b0                                              # B0: metadatos, sklearn, segundos
make train ARGS="+experiment=b1_resnet50_224 train.seed=0"    # B1: ResNet50 a 224 px (GPU)
make train ARGS="+experiment=b1_resnet50_224_sampler train.seed=0"   # B1 con muestreo ponderado
make train ARGS="+experiment=prep_b_divide255"                # F2.6: condición B
make f2-report                                                # reports/f2_baselines.md y preprocessing_experiment.md
```

Cada corrida deja en su directorio de Hydra `checkpoints/`, `metrics.json` (métricas, IC por
paciente, historial por época, colapsos, SHA del commit y de los splits), `curves.json`,
`val_predictions.csv`, `figures/` y `summary.md`. Las corridas de Kaggle se copian a
`reports/runs/<run_name>/` y `make f2-report` las agrupa por la clave `experiment` de su config.

- **DataModule** (`melanoma.data.datamodule`): normalización, interpolación y tamaño de entrada
  desde el `data_config` de la fábrica; aumentación solo en entrenamiento; `test_dataloader()`
  lanza `LockedTestSplitError`. Rutas por entorno en `data.paths.{local,kaggle}` (`data.env=auto`).
- **Desbalance**: `train.pos_weight` (`auto` = negativos/positivos ≈ 55) o `data.sampler=weighted`.
- **Detector de colapso**: al final de cada validación, si la desviación estándar de las
  probabilidades cae por debajo de `train.collapse_std_threshold` o el AUROC queda en ~0.5, se
  registra `COLAPSO DETECTADO` en el log y `val/collapsed=1`.
- **Evaluación** (`melanoma.eval`): AUC-ROC, AUPRC (primaria), sensibilidad/especificidad a
  nivel fijo, VPP/VPN, matriz de confusión, bootstrap de 2,000 remuestreos por paciente y curvas a
  archivo. La exactitud no existe en el módulo.
- **W&B**: `train.wandb.enabled=true`, proyecto `melanoma-triage`, llave en `WANDB_API_KEY`
  (Kaggle Secrets). Nombre de corrida `{modelo}-{resolución}-s{semilla}-{sha}`.
- **Kaggle**: `notebooks/kaggle_prepare_512.ipynb` (una vez: dataset `melanoma-isic2020-512` y
  verificación de `sha256_resized`) y `notebooks/kaggle_train.ipynb` (clona el repo en un SHA,
  verifica `SHA256SUMS`, entrena con `configs/`). Antes de mandarlos a Kaggle:
  `make check-notebooks` los ejecuta de principio a fin en un sandbox local (venv limpio, clon
  del árbol de trabajo, `/kaggle/input` sintético, intérprete ya corriendo). En CI,
  `tests/test_notebooks.py` verifica sus imports de `melanoma.*` y que `src/` entre en
  `sys.path` antes del primer import.
- **Kaggle por API, sin navegador**: `make kaggle ARGS="push b1-s0 --sha <SHA> --wait"` empuja
  el notebook como kernel (metadata generado desde `configs/kaggle.yaml`), espera, baja la
  salida a `reports/runs/b1-s0/` y muestra el log si falló. También `status`, `wait`, `output`,
  `logs`, `list`, `dataset-images` (publica las imágenes de 512 px como un solo zip) y
  `sync-wandb` (sube las corridas offline de W&B). Las siete corridas de F2 están en `runs:`.

## Matriz, evaluación clínica, explicabilidad, paquete e interfaz (F3–F7)

```bash
make f3-report                 # reports/f3_matrix.md a partir de reports/runs/
make f4-report                 # reports/f4_clinical_evaluation.md (el test ya se abrió; no se vuelve a abrir)
make f3b-all                   # F3b: verifica los 9 checkpoints, cachea logits, candidatos, apilador, reports/f3b_ensemble.md
make f7b-icons f7b-visual      # F7b: favicons desde el símbolo; contraste de tokens y capturas (reports/f7b_visual.md)
make demo                      # demo local en http://127.0.0.1:8010 con la imagen de CI y el paquete real (docs/DEMO.md)
make f5-all                    # CAM, solapamiento con la lesión, artefactos, figuras y reports/f5_explainability.md
make export-bundle             # models/bundle/ desde el checkpoint de F3 (ONNX + calibración + umbrales + CAM)
make verify-bundle             # paridad ONNX vs PyTorch → reports/f6_parity.json
make test-bundle               # paquete de prueba con pesos aleatorios (CI y Docker)
make api                       # API + interfaz en http://127.0.0.1:8000 (MODEL_BUNDLE_DIR=models/bundle)
make docker-api                # imagen melanoma-api; make docker-run BUNDLE=models/bundle
make web-dev                   # interfaz en modo desarrollo (Vite)
make test-local                # pruebas @local con el checkpoint real y models/bundle
make f7-screenshots            # capturas de la interfaz en reports/figures/f7_ui_*.png
```

El paquete real se publica como asset del release `model-…` de GitHub (con su `.sha256`);
se descomprime en `models/`. Contrato de la API en `docs/API.md`.

## Estructura del repositorio

```
.github/workflows/   CI: ruff, pytest, humo, build de la API y límite de 650 MB sin comprimir
configs/             Configuración Hydra: data/, model/, train/, experiment/ y composiciones raíz (config, prepare, smoke, baseline_b0)
src/melanoma/        Paquete Python: data (manifiesto, dedup, splits, resize), models (fábrica timm), train, eval, explain, export, utils
services/api/        API de inferencia FastAPI + onnxruntime (grupo `api`, sin torch ni core) y su Dockerfile
services/web/        Interfaz web (F7: Vite + React + TS), servida por la API bajo /
data/manifests/      isic2020.csv, una fila por imagen con SHA256 (versionado)
data/splits/         train.txt, val.txt, test.txt y SHA256SUMS (versionados)
data/raw/, data/processed/   Imágenes originales y redimensionadas (NO versionadas)
reports/             Reportes por fase (F1–F6), metrics/, predictions/, runs/ (salidas de Kaggle) y figures/
notebooks/           kaggle_setup.ipynb (procedencia), kaggle_prepare_512.ipynb (F2.0), kaggle_train.ipynb (F2.8, F3)
kaggle/              Metadatos del dataset privado de Kaggle (manifiesto + splits)
scripts/             Pipeline de datos, entrenamiento, reportes por fase, evaluación del test y DDI, exportación, capturas y utilidades de CI
tests/               Pruebas rápidas sin descargas (las que necesitan datos se saltan si faltan)
docs/                DATA.md (licencia, procedencia), API.md, f4_protocol.yaml, hardware.md, historial.md, specs/ por fase
logs/                test_set_access.log (versionado) y salidas de corridas (no versionadas)
```

Regla del proyecto: **cero constantes de configuración en `src/`**. Tamaños de imagen,
tasas de aprendizaje y rutas viven solo en `configs/`. La normalización de píxeles
(`mean`, `std`, `input_size`) proviene únicamente del `data_config` que devuelve
`melanoma.models.factory.build_model`.

## Datos: ISIC 2020

Detalles de licencia, atribución y procedencia en `docs/DATA.md`. El pipeline completo de F1
corre con `make data-all` (o paso por paso: `data-verify`, `data-manifest`, `data-dedup`,
`data-splits`, `data-resize`, `data-eda`) y está parametrizado en `configs/data/isic2020.yaml`.

Descarga (fuente oficial, ~24.7 GB; el ZIP se verifica por tamaño y las imágenes por SHA256):

```bash
mkdir -p data/raw/isic2020 && cd data/raw/isic2020
for f in ISIC_2020_Training_JPEG.zip ISIC_2020_Training_GroundTruth_v2.csv ISIC_2020_Training_Duplicates.csv; do
  curl -L -O "https://isic-challenge-data.s3.amazonaws.com/2020/$f"
done
```

### Splits agrupados por paciente

70 / 15 / 15 por paciente, estratificados por «paciente con al menos un melanoma», semilla
`20260904`. Un `image_id` por línea, ordenados. Conteos alcanzados en `reports/splits_report.md`.
SHA256 de los archivos versionados (verificado por `tests/test_splits.py`):

```
701333b2450c363b1ab1b5a9422d3d223d243e1b3af2d643b05f6b86f711968c  train.txt
b7f727d6cf70d7a12be136e3b7046b42c725eaf5541aadc0723fbac09941ffb1  val.txt
7dedecdd0ebf1e8997eb4be12fe71af04475de2bd1b0da5d6fde8440a7742316  test.txt
```

### Conjunto de prueba bloqueado

`data/splits/test.txt` se usa **como máximo dos veces en todo el proyecto**, ambas desde
`scripts/evaluate_test.py` (F4 y F4b; se niega a correr si la bitácora ya tiene dos líneas), y
cada acceso se anota en `logs/test_set_access.log`
(primer acceso: 2026-09-18, evaluación clínica de F4; segundo y último: 2026-10-26, ensamble de
F4b bajo `docs/f4b_protocol.yaml`). **El presupuesto está agotado: no existe un tercer acceso.** Ningún
módulo de `src/` puede referenciarlo: lo vigila `tests/test_test_split_isolation.py` en CI.

### Kaggle

El entrenamiento corre en Kaggle. Ahí se adjunta la distribución oficial de la competencia
(`siim-isic-melanoma-classification`) y un dataset privado con solo el manifiesto y los splits
(`make kaggle-dataset KAGGLE_USERNAME=<usuario>`; publicado como
`edgaronti26/melanoma-isic2020-splits`). `notebooks/kaggle_setup.ipynb` verifica el SHA256 de
200 imágenes contra el manifiesto y falla si alguno no coincide; corrido el 2026-09-04 con
200/200 coincidencias (ver `docs/DATA.md`).

## Licencias y atribución

- **Código:** MIT (ver `LICENSE`). Para citar el proyecto: `CITATION.cff`.
- **Datos:** el ISIC 2020 Challenge Dataset se distribuye bajo
  [CC-BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). Cita requerida:

  > International Skin Imaging Collaboration. SIIM-ISIC 2020 Challenge Dataset.
  > International Skin Imaging Collaboration. https://doi.org/10.34970/2020-ds01 (2020).
  >
  > Rotemberg, V., Kurtansky, N., Betz-Stablein, B., et al. A patient-centric dataset of
  > images and metadata for identifying melanomas using clinical context.
  > *Sci Data* 8, 34 (2021). https://doi.org/10.1038/s41597-021-00815-z

- **Pesos y artefactos derivados:** cualquier modelo entrenado sobre datos CC-BY-NC hereda
  la restricción **no comercial**. Los checkpoints, archivos ONNX y el despliegue de la API
  tienen que ser no comerciales y mantener la atribución anterior.

## Estado del proyecto

| Fase | Contenido | Estado |
|---|---|---|
| F0 | Esqueleto, entorno, CI, prueba de humo | Cerrada (`docs/specs/F0.md`) |
| F1 | Manifiesto, deduplicación, splits por paciente, bloqueo del test, Kaggle | Completa: 10/10 criterios en verde, cerrada el 2026-09-04 (`docs/specs/F1.md`) |
| F2 | Líneas base B0/B1, DataModule, evaluación, experimento de preprocesamiento, Kaggle por API | Cerrada el 2026-09-17: 12/12 criterios en verde (`docs/specs/F2.md`) |
| F3 | Matriz de modelos, ablación de resolución, anclaje en literatura | Cerrada el 2026-09-18: 9/9 criterios; modelo final A1 = EfficientNetV2-S a 224 px, semilla 0 (`docs/specs/F3.md`, `reports/f3_matrix.md`) |
| F4 | Evaluación clínica: test bloqueado, calibración, umbral, subgrupos, DDI, limitaciones | Cerrada el 2026-10-15: 10/10 criterios; test abierto una vez el 2026-09-18 (AUC-ROC 0.834, AUPRC 0.096); el acceso restante está asignado a F4b; limitaciones en `docs/f4_limitations.md` (`docs/specs/F4.md`, `reports/f4_clinical_evaluation.md`) |
| F5 | Explicabilidad: CAM ≡ Grad-CAM (contrato numpy para F6), prueba de cordura, solapamiento con la lesión, artefactos por perturbación | Cerrada el 2026-09-21: 10/10 criterios (`docs/specs/F5.md`, `reports/f5_explainability.md`) |
| F6 | Paquete de modelo (ONNX opset 17 + calibración + umbrales + pesos CAM + manifiesto SHA256), paridad con PyTorch, API FastAPI/onnxruntime sin torch, Docker ~420 MB sin comprimir (~155 MB comprimida); preprocesamiento en dos etapas con paridad exacta hasta con originales de 6,000 px | Cerrada el 2026-09-21: 10/10 criterios (`docs/specs/F6.md`, `docs/API.md`) |
| F7 | Interfaz web (Vite + React + TS) servida por la API: análisis con probabilidad calibrada, tasa base, recomendación, CAM y ficha del modelo con las limitaciones | Cerrada el 2026-10-15: 10/10 criterios (`docs/specs/F7.md`) |
| F3b/F4b | Ensamble de los nueve checkpoints de F3, TTA, metadatos apilados; segundo y último acceso al test con protocolo propio | F3b el 2026-10-23: Eᵍ = E1 (A1 ×3, sin TTA), metadatos no. F4b el 2026-10-26, test abierto por segunda y última vez: AUC-ROC 0.843 [0.804, 0.881] y AUPRC 0.113 [0.076, 0.179] contra 0.834 y 0.096 del modelo único; por el criterio fijado antes de abrir, **se despliega el ensamble** (F6b) (`docs/specs/F3b-F4b.md`, `reports/f3b_ensemble.md`, `reports/f4_clinical_evaluation.md` §11) |
| F6b | Paquete con el ensamble (tres ONNX, manifiesto verificado contra `docs/f4b_protocol.yaml`), API con promedio de logits y CAM promediado, `/model-info` con tabla lado a lado, release `model-28a90b4-4264e888` | Hecha el 2026-10-26: 8/8 criterios; paridad máx 2.2e-5, p50 99 / p95 118 ms, imagen 437 MB sin comprimir (`docs/specs/F6b.md`, `reports/f6b_parity.json`, `reports/f6b_latency.md`) |
| F7b | Sistema visual: tokens, Inter empaquetada, símbolo y favicons, componentes de análisis y ficha, contraste AA; ajuste del 2026-10-27 con colores institucionales (azul de la Facultad, morado del escudo), contenedor de 1360 px y logos en el pie | Hecha el 2026-10-26, ajustada el 2026-10-27 (F7b.6 y F7b.7): 8/8 criterios; 14 pares de contraste ≥ AA; tres pruebas nuevas (`docs/specs/F7b.md`, `reports/f7b_visual.md`) |
| F8 | Despliegue: imagen en ghcr publicada por el CI, `deploy/` (compose + Caddy + install.sh), objetivos `make deploy*`, Lightsail + Cloudflare + Let's Encrypt | En curso desde 2026-10-26: F8.1 y F8.2 hechos; F8.3 detenido en la pausa obligatoria (falta el perfil `personal` de la CLI de AWS); demo local en `make demo` (`docs/specs/F8.md`, `docs/DEPLOY.md`, `docs/DEMO.md`) |
| F9 | Documento y defensa | Pendiente |

Diagnóstico del hardware de desarrollo: `docs/hardware.md`.

## Imagen Docker: límite de 650 MB sin comprimir

La imagen de la API (`services/api/Dockerfile`) debe medir **menos de 650 MB sin comprimir**
(`make docker-size`, mismo criterio en CI: suma de capas de `docker history`). El límite subió
de 500 a 650 MB en F6b por margen para el ensamble (el paquete se monta, no va dentro; la imagen
no crece por él). La regla sigue cumpliendo su función: `torch` instalado ocupa 741 MB, así que
colarlo en el grupo `api` sigue haciendo fallar el CI. Tamaño actual: ~440 MB sin comprimir,
~155 MB comprimida.
