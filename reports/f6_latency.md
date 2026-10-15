# F6 — Latencia de la API en CPU

_Generado por `scripts/bench_api.py` el 2026-09-21._

- Máquina: AMD Ryzen 7 250 w/ Radeon 780M Graphics, 16 hilos lógicos, Linux 6.18.33.2-microsoft-standard-WSL2.
- Modo: en proceso (TestClient), 4 hilos intra-op. Modelo `c62a515-e0ecf981`; imagen `ISIC_0096201.jpg` (512×288 JPEG, 47 KB).
- 200 peticiones secuenciales a `POST /predict`, lote 1, tras 5 de calentamiento.

## Latencia total por petición (cliente, ms)

| p50 | p95 | p99 | media | máx |
|--:|--:|--:|--:|--:|
| 35.2 | 45.2 | 52.0 | 36.7 | 58.0 |

La API **cumple** el objetivo p95 < 500 ms.

## Desglose por etapa (medido dentro de la API, ms)

| etapa | p50 | p95 | p99 | media |
|:--|--:|--:|--:|--:|
| decode_stage1 | 0.9 | 1.3 | 1.8 | 1.0 |
| preprocess | 1.0 | 1.3 | 1.5 | 1.0 |
| onnx | 23.9 | 33.6 | 37.8 | 25.4 |
| cam | 0.1 | 0.2 | 0.3 | 0.1 |
| render | 6.9 | 8.6 | 9.2 | 7.1 |
| api_total | 33.2 | 43.6 | 49.8 | 34.8 |

`api_total` es el tiempo dentro del endpoint (desde recibir los bytes hasta serializar); la
diferencia con la latencia del cliente es el transporte y el análisis del multipart.
`render` es el PNG del CAM superpuesto (base64); no corre cuando el mapa es nulo.
