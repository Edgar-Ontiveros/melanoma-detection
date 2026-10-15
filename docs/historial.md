# Reescritura del historial de git (2026-10-15)

## Qué se hizo y por qué

El 2026-10-15, antes de la entrega, se reescribió el historial de `main` con
`git filter-repo` para **normalizar los metadatos de autoría**:

- Autor y committer de los 51 commits quedan como
  `Edgar Eduardo Ontiveros Lara <edgarontiverosfm@gmail.com>` (antes `Edgar Ontiveros`, mismo
  correo).
- Se quitaron de los mensajes las líneas de metadatos de herramientas (trailers de sesión en 4
  commits y una línea sobre configuración local en otro).
- Cada asunto quedó en ≤ 72 caracteres, en infinitivo; lo que no cabía pasó al cuerpo. Los
  SHAs citados dentro de los mensajes se tradujeron a los nuevos.

## Qué no cambió

**Ningún contenido, fecha ni orden de commits cambió.** Se verificó, commit por commit en el
mismo orden, que el árbol (`%T`), la fecha de autor y la fecha de commit son idénticos antes y
después. Solo cambian los mensajes y los nombres, y con ellos los SHAs.

## Mapa de SHAs

`docs/commit-map.txt` es el mapa viejo → nuevo tal como lo produce `git filter-repo` (SHA
completos, una línea por commit). Cualquier SHA viejo que aparezca fuera del repositorio
(W&B, kernels y datasets de Kaggle, nombres de corrida) se traduce con él. Como los árboles
son idénticos, el commit nuevo contiene exactamente el mismo código que el viejo.

## SHAs dentro del repositorio

Se remapearon las referencias a commits en `docs/` (specs, `API.md`, `DATA.md`), `reports/`
(`*.md`, `*.json`, `metrics/`), `logs/test_set_access.log` y en el manifiesto del paquete.
Se conservaron, a propósito, los SHAs que forman parte del **nombre** de un artefacto que
existe o existió con ese nombre:

- nombres de corrida y sus rutas (`reports/runs/…`, p. ej. `tf_efficientnetv2_s-224-s0-e153979`),
  que son también los nombres en W&B y en Kaggle;
- el nombre del checkpoint `tf_efficientnetv2_s-224-s0-e153979-04-0.0000.ckpt` (archivo real
  en el dataset de Kaggle y en `configs/f4.yaml`, `f5.yaml`, `f6.yaml`);
- el release retirado `model-6c330a8-e0ecf981`;
- `docs/f4_protocol.yaml` y su copia literal en `reports/f4_clinical_evaluation.md` (ver abajo).

`reports/f3_matrix.md` se genera desde `reports/runs/*/metrics.json`, que conservan los SHAs
originales; `scripts/f3_report.py` los traduce con `docs/commit-map.txt`, así que la columna de
commit muestra los SHAs nuevos al regenerarse (el nombre de corrida conserva el original).

## Bitácora del test y protocolo

`docs/f4_protocol.yaml` no se modificó: su SHA256,
`8c45394e1219d67706076ec9a407427b15616386635b7df52be1969637515e93`, no depende de git y sigue
coincidiendo con el `protocol_sha256` anotado en `logs/test_set_access.log`. Es el ancla
verificable de la bitácora:

```bash
sha256sum docs/f4_protocol.yaml
```

En la línea de la bitácora solo cambió `git=be931a6` → `git=7fc5462` (mismo árbol). El orden
se conserva: el protocolo se commiteó solo en `16b6a04` (antes `23d817a`) el 2026-09-18 a las
15:48:29 −0600, y el acceso al test quedó registrado a las 22:10:55 UTC (16:10:55 −0600).

## Release del paquete de modelo

El release `model-4e7ab61-e0ecf981` pasó a `model-c62a515-e0ecf981`, con el tag sobre
`cade2ed` (antes `d7b9b0f`). En `models/bundle/manifest.json` cambian solo `model_version`
(`c62a515-e0ecf981`) y `git_sha` (`c62a515`). El ONNX, la calibración, los umbrales, los pesos
CAM y las métricas son los mismos archivos, con los mismos SHA256 en el manifiesto. El tarball
nuevo `melanoma-bundle-c62a515-e0ecf981.tar.gz` tiene SHA256
`ec51a043636d4b2d77f74d7943186facfd7b8600dd5b7aca9c8b562ef977ae4c`.
