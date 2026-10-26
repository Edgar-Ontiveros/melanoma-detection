# F3b — Ensamble, TTA y metadatos · F4b — Segundo y último acceso al test

Especificación de la fase. Guardar como `docs/specs/F3b-F4b.md`.

**Duración estimada:** 1 semana. Sin GPU: todos los checkpoints ya existen.
**Depende de:** F3 (9 checkpoints en Kaggle), F4 (primer acceso, protocolo, resultados).
**Bloquea:** F6b (paquete con varios modelos), F8.

---

## Por qué existe esta fase

F4 dio, con un modelo único, AUC-ROC 0.834 y especificidad 0.428 a sensibilidad 0.965. Las
tres mejoras estándar que F3 y F4 dejaron fuera de alcance — ensamble, TTA y metadatos —
cuestan cero GPU porque los nueve checkpoints de F3 ya están entrenados. Esta fase las
evalúa sobre validación con una regla escrita de antemano, congela lo que gane, y usa el
**segundo y último acceso** al conjunto de prueba.

**Reglas que no se negocian:**

1. Todo se elige sobre validación. Nada se mira en el test hasta el protocolo congelado.
2. El resultado de F4 (modelo único) **se sigue reportando** junto al de F4b. La tesis
   muestra los dos. Un lector debe poder ver cuánto aportó cada mejora.
3. Después de F4b, el presupuesto de accesos al test queda en cero. `evaluate_test.py` se
   niega a correr si `logs/test_set_access.log` ya tiene dos líneas. Si el ensamble sale
   peor que el modelo único, se reporta así y se despliega el modelo único.

---

## Contexto fijado

| Aspecto | Valor |
|---|---|
| Checkpoints disponibles | A1 ×3 (224 px), M1 ×3 (384 px), M2 ×3 (384 px), en las salidas de los kernels de F3 |
| Resultado a superar (F4, test) | AUC 0.834 [0.795, 0.872], AUPRC 0.096, spec@sens0.95 0.481, en τ₉₅: sens 0.965 / spec 0.428 |
| Umbral de ruido | 0.02 en AUC-ROC y AUPRC (F2/F3) |
| Presupuesto de latencia en CPU | p95 < 1.5 s (arquitectura); objetivo < 1 s |
| Accesos al test | 1 usado; **este es el último** |

---

## F3b.1 — Recuperar los checkpoints

`kaggle_run.py checkpoint <corrida>` para las 8 corridas restantes (`a1-s1`, `a1-s2`,
`m1-s{0,1,2}`, `m2-s{0,1,2}`). Registrar el SHA256 de cada uno en
`reports/f3b_checkpoints.json`. Verificar que cada checkpoint, evaluado sobre validación,
reproduce el AUC de `reports/f3_matrix.md` con diferencia < 0.005 (misma máquina, CPU): si
no, ese checkpoint no es el que se reportó y no se usa.

Van a `data/models/` (fuera de git). ~240 MB cada uno.

---

## F3b.2 — Logits en caché

Para cada uno de los 9 modelos, sobre las 4,963 imágenes de validación, guardar los logits
con **cuatro vistas**: original, espejo horizontal, espejo vertical, ambos. Un archivo
`reports/predictions/f3b_val_logits.npz` con forma `[9, 4, 4963]`.

Es la única inferencia pesada: 9 × 4 × 4,963 ≈ 180 mil pasadas. M2 a 384 px es lo lento;
estimar ~1 h de CPU en total. Todo lo demás de F3b son operaciones sobre este archivo.

---

## F3b.3 — Candidatos

**Ensamble = promedio de logits** (no de probabilidades: el promedio de logits es lo
estándar y conmuta bien con Platt).

| Candidato | Modelos | GFLOPs por imagen (1 vista) |
|---|---|---|
| E0 (referencia) | A1 semilla 0 | 2.9 |
| E1 | A1 ×3 | 8.7 |
| E2 | A1 ×3 + M2 ×3 | 48 |
| E3 | A1 ×3 + M1 ×3 + M2 ×3 | 73 |

Cada uno con TTA ∈ {ninguno, 2 vistas (original + espejo horizontal), 4 vistas}. Doce
combinaciones más la referencia. GFLOPs × vistas = costo de inferencia.

Para cada combinación, sobre validación: AUC-ROC, AUPRC, spec@sens0.90, spec@sens0.95, con
IC por bootstrap a nivel paciente (2,000 remuestreos), y el costo.

### Regla de decisión, escrita antes de ver los números

1. Se ordena por **AUPRC medio** y después por **spec@sens0.90**.
2. Dos candidatos que difieran en menos de **0.02** en AUC-ROC **y** en AUPRC empatan; entre
   empatados gana el **más barato**.
3. Restricción dura: costo estimado de inferencia < **1 s** en la laptop (extrapolado de la
   latencia de F6: 2.9 GFLOPs ≈ 30 ms de ONNX). Un candidato que la viole queda fuera
   aunque gane.
4. **Eᵍ es el más barato de los candidatos que (a) empatan con el líder, (b) cumplen la
   restricción de costo y (c) superan a E0 por más de 0.02 en AUPRC.** Si ese conjunto está
   vacío, **el ensamble no aporta**, F4b no se ejecuta y el acceso se conserva.

   (Corrección del 2026-10-22, antes de ver ningún número real: la redacción anterior
   preguntaba si «alguna combinación» superaba a E0, y el ganador por las reglas 1–3 podía ser
   un empatado más barato que no lo superaba.)

El candidato ganador se llama **Eᵍ**.

---

## F3b.4 — Metadatos apilados

Con Eᵍ fijo, un segundo modelo pequeño encima:

- **Entradas:** logit de Eᵍ, edad (estandarizada, con indicador de faltante), sexo (one-hot
  con faltante), sitio anatómico (one-hot con faltante). Las mismas variables de B0.
- **Modelo:** regresión logística con regularización L2, coeficiente elegido por validación
  cruzada. Nada más complejo: con 88 positivos, más parámetros es sobreajuste.
- **Evaluación:** **validación cruzada de 5 pliegues agrupada por paciente** sobre
  validación. Nunca se entrena y evalúa en las mismas imágenes.
- **Comparar** AUC-ROC, AUPRC y spec@sens0.95 de la VC contra Eᵍ solo (evaluado en los
  mismos pliegues).

### Regla

Los metadatos se despliegan **solo si** la VC muestra **≥ +0.02 en AUC-ROC o ≥ +0.05 en
spec@sens0.95** sobre Eᵍ. Si no, se reporta la ganancia medida y no se usan. El umbral es
alto a propósito: desplegarlos obliga a la interfaz a pedir tres datos por paciente, y eso
solo se justifica si el modelo cambia de verdad.

Si se despliegan, el apilador final se ajusta sobre toda la validación y se congela junto
con Eᵍ. En la API, los metadatos son **opcionales**: sin ellos, la respuesta usa Eᵍ solo y
lo dice.

---

## F3b.5 — Calibración y umbrales, otra vez

Sobre validación, con el modelo final de F3b (Eᵍ o Eᵍ + apilador):

- Platt ajustado sobre los logits del ensamble (o sobre la salida del apilador).
- τ₉₅ y τ₉₀ por bootstrap a nivel paciente, mediana de 2,000, como en F4.
- **Advertencia obligatoria en el reporte:** validación ya se usó para elegir Eᵍ, ajustar
  el apilador, calibrar y fijar el umbral. Su optimismo es mayor que en F4. El test es la
  única estimación limpia, y por eso existe F4b.

---

## F3b.6 — Reporte

`reports/f3b_ensemble.md`, generado por script:

1. Verificación de los 9 checkpoints contra F3.
2. Tabla de las 13 combinaciones con IC y costo; Eᵍ marcado y la regla aplicada.
3. Figura: AUPRC contra costo, con la frontera.
4. Metadatos: ganancia por VC, decisión.
5. Calibración y umbrales nuevos.
6. **Declaración del modelo final de F3b** con los SHA256 de todo.

---

## F4b — Segundo y último acceso al test

### Protocolo

`docs/f4b_protocol.yaml`, commiteado **antes** de ejecutar `evaluate_test.py --protocol`
(el guardarraíl y la opción `--protocol` se commitean antes, porque no dependen de los valores
del protocolo; lo que espera al protocolo es la ejecución, no el código. Decisión del 2026-10-22):

```
models: [lista de checkpoints con SHA256]
tta: [vistas]
ensemble: logit_mean
stacker: {enabled: bool, coefficients: [...], features: [...]} | null
calibration: {method: platt, a, b}
thresholds: {tau_95, tau_90}
access_number: 2
budget_after: 0
deployment_rule: "El ensamble se despliega solo si … (el criterio de despliegue de abajo)"
```

### Guardarraíles nuevos

- `evaluate_test.py --protocol docs/f4b_protocol.yaml` acepta un protocolo distinto al
  de F4 sin borrar nada del primero.
- Se niega a correr si la bitácora ya tiene **dos** líneas.
- `test_second_access_is_last`: con una bitácora simulada de dos líneas, el script aborta.
- El protocolo de F4 (`docs/f4_protocol.yaml`) y sus resultados no se tocan.

### Ejecución

Una vez. Igual que F4: bitácora antes de leer, calibración y umbrales congelados, bootstrap
por paciente, subgrupos, sin reajustes.

### Reporte

`reports/f4_clinical_evaluation.md` gana una sección, **no se reescribe**: "Resultado con
ensamble (segundo acceso)". Tabla lado a lado:

| | Modelo único (F4) | Ensamble (F4b) | Diferencia |
|---|---|---|---|
| AUC-ROC | 0.834 [IC] | … | … |
| AUPRC | 0.096 [IC] | … | … |
| Sens / spec en τ₉₅ | 0.965 / 0.428 | … | … |
| spec@sens0.95 | 0.481 | … | … |
| ECE con Platt congelada | 0.0006 | … | … |
| Costo de inferencia | 2.9 GFLOPs | … | … |

Y un párrafo que diga qué aportó cada cosa, con los números de validación de F3b para
descomponerlo (seeds, arquitecturas, TTA, metadatos).

**Criterio de despliegue (fijado el 2026-10-26, antes de abrir el test):** El ensamble se
despliega solo si en el test su AUC-ROC y su AUPRC no son menores que las del modelo único
(F4). Si cualquiera de las dos es menor, se despliega el modelo único y el ensamble solo se
reporta. Si es el modelo único, se queda como está.

---

## Pruebas a agregar

| Prueba | Qué verifica |
|---|---|
| `test_ensemble_mean_logits` | El promedio es de logits, no de probabilidades |
| `test_tta_views_are_involutions` | Espejar dos veces devuelve la imagen original |
| `test_stacker_cv_grouped_by_patient` | Ningún paciente aparece en entrenamiento y prueba del mismo pliegue |
| `test_decision_rule_f3b` | Con una tabla sintética, la regla elige el más barato entre empatados y excluye los que violan el costo |
| `test_second_access_is_last` | Bitácora con dos líneas → el script aborta antes de leer nada |

---

## Criterios de aceptación

1. Los 9 checkpoints descargados, con SHA256, y cada uno reproduce su AUC de F3 (< 0.005).
2. Logits en caché para 9 modelos × 4 vistas.
3. Tabla de 13 combinaciones con IC y costo; Eᵍ elegido por la regla; si nada supera a E0
   por 0.02 en AUPRC, se declara y F4b no corre.
4. Metadatos evaluados por VC agrupada; decisión por la regla.
5. Platt y umbrales nuevos sobre validación, con la advertencia de optimismo.
6. `docs/f4b_protocol.yaml` commiteado antes de ejecutar el segundo acceso; el historial y la
   bitácora lo muestran.
7. Segundo acceso ejecutado una vez; bitácora con exactamente dos líneas; guardarraíl de
   "no hay tercero" probado.
8. Tabla lado a lado en el reporte de F4, con el modelo único intacto.
9. `make ci` en verde; push.

---

## Fuera de alcance

- **ISIC 2019 u otros datos.** Requiere deduplicación entre datasets y reentrenar. Se
  decide después, con el resultado de F4b en la mano.
- **Reentrenar nada.** Solo se combinan modelos que ya existen.
- **Un tercer acceso al test.** No existe.
- **Modificar los resultados de F4.** Se agregan; no se reemplazan.

---

## Orden de trabajo

**Sesión 1:** F3b.1 y F3b.2. Descargar, verificar, cachear logits (la hora de CPU).
**Sesión 2:** F3b.3. Los 13 candidatos y la regla.
**Sesión 3:** F3b.4 y F3b.5. Metadatos, calibración, umbrales, reporte de F3b.
**Pausa:** revisar el protocolo de F4b antes de ejecutarlo.
**Sesión 4:** F4b. El último acceso.

---

## Qué esperar

E2 (A1 ×3 + M2 ×3) con 2 vistas es el candidato más probable: la diversidad entre
EfficientNet y ConvNeXt suele valer más que tres semillas del mismo backbone. Costo ≈ 100
GFLOPs, ~0.5 s en CPU.

Sobre validación, AUC 0.85–0.87 y spec@sens0.95 0.52–0.60. Sobre el test, un poco menos,
por el optimismo acumulado de validación. Los metadatos probablemente **no** pasen el
umbral de despliegue: B0 tiene señal, pero mucha ya está en la imagen.

Si el test dice 0.86 y 0.55, tienes un ensamble que aporta +0.03 y +0.10 sobre el modelo
único, medido honestamente, con ambos números en la tesis. Si dice 0.84 y 0.46, tienes la
evidencia de que el ensamble no aporta con estos datos — también publicable, y también
honesto.

Lo que **no** cambia con nada de esto: el modelo sigue siendo una herramienta de
priorización, no un filtro autónomo. Con 0.55 de especificidad refieres a 45 de cada 100
sanos en lugar de 57. Mejor; no distinto en naturaleza.
