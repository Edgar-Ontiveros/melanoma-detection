# F6b — Latencia de la API en CPU (ensamble de tres)

_Generado por `scripts/bench_api.py` el 2026-10-26._

- Máquina: AMD Ryzen 7 250 w/ Radeon 780M Graphics, 16 hilos lógicos, Linux 6.18.33.2-microsoft-standard-WSL2.
- Modo: en proceso (TestClient), 4 hilos intra-op. Modelo `28a90b4-4264e888`; imagen `ISIC_0096201.jpg` (512×288 JPEG, 47 KB).
- 200 peticiones secuenciales a `POST /predict`, lote 1, tras 5 de calentamiento.

## Latencia total por petición (cliente, ms)

| p50 | p95 | p99 | media | máx |
|--:|--:|--:|--:|--:|
| 98.6 | 118.3 | 128.1 | 101.5 | 142.7 |

La API **cumple** el objetivo p95 < 200 ms.

## Desglose por etapa (medido dentro de la API, ms)

| etapa | p50 | p95 | p99 | media |
|:--|--:|--:|--:|--:|
| decode_stage1 | 1.1 | 1.4 | 1.9 | 1.1 |
| preprocess | 1.1 | 1.4 | 1.7 | 1.1 |
| onnx | 78.9 | 96.9 | 103.0 | 81.7 |
| cam | 0.3 | 0.4 | 0.6 | 0.3 |
| render | 14.6 | 18.2 | 19.8 | 15.2 |
| api_total | 96.6 | 116.3 | 125.6 | 99.4 |

`api_total` es el tiempo dentro del endpoint (desde recibir los bytes hasta serializar); la
diferencia con la latencia del cliente es el transporte y el análisis del multipart.
`render` es el PNG del CAM superpuesto (base64); no corre cuando el mapa es nulo.
