# F7b — Sistema visual

Especificación de la fase. Depende de F7 y F6b. No toca la API, el modelo ni los textos de la recomendación.

## Objetivo
Interfaz limpia, elegante y sobria: herramienta clínica, no landing page. Un solo acento, filetes en lugar de sombras, jerarquía tipográfica real, cero adornos. Debe verse hecha por una persona con criterio, no generada.

## Reglas que no cambian (F7)
Cero constantes del modelo en el frontend. Tarjeta de recomendación sin números. Aviso desde la API. Sin recursos externos: las fuentes se empaquetan. Contraste AA. Teléfono en vertical. Sin semáforo. Sin animaciones decorativas. Escudo UACH solo en la atribución de /modelo; eo.svg solo en el pie.

## F7b.1 — Tokens (`services/web/src/styles/tokens.css`, variables CSS; ningún color ni tamaño fuera de este archivo)
Color: --bg #FFFFFF · --surface #F8FAFC · --border #E2E8F0 · --border-strong #CBD5E1 · --text #0F172A · --text-2 #475569 · --accent #1D4ED8 · --accent-hover #1E40AF · --accent-tint #EFF6FF · --accent-tint-border #BFDBFE. Foco: anillo 2 px --accent con 2 px de separación.
Tipografía: Inter variable, subconjunto latín, woff2 empaquetado en `services/web/public/fonts/` (licencia OFL incluida), fallback system-ui; `font-feature-settings: "tnum"` en todo número. Escala: 12 (etiquetas, mayúsculas, tracking 0.04em, peso 600) · 13 (ayuda) · 14 (UI) · 15 (cuerpo) · 17 (wordmark, 600) · 22 (recomendación, 600) · 52 (probabilidad, 700, tracking −0.02em, interlínea 1). Interlínea de cuerpo 1.5. Identificadores en monoespaciada del sistema.
Espacio: 4/8/12/16/24/32/48. Contenedor 1120 px, márgenes 24. Radios: 10 tarjetas, 8 botones, 6 chips, 999 barra. Bordes 1 px. Sin sombras salvo el modal (0 8px 24px rgba(15,23,42,.12)). Movimiento: 150 ms ease solo en hover/foco/opacidad; respetar prefers-reduced-motion.
Textos: frases cortas, sin exclamaciones, sin emojis, sin "potenciado por IA". Números en español ("12,2 %", espacio fino indivisible antes del %).

## F7b.2 — Componentes
- Encabezado 64 px, borde inferior --border: símbolo (F7b.3) a 20 px en currentColor + wordmark "Detección asistida de melanoma" 17/600; a la derecha, enlaces 14/500, el activo con subrayado de 2 px --accent. No fijo.
- Botones de 40 px: primario (fondo --accent, texto blanco, radio 8, 14/500); secundario (fondo --bg, borde --border-strong); fantasma (texto --accent, sin borde). Variante de 36 px dentro de tarjetas.
- Zona de carga: borde 1 px discontinuo --border-strong, fondo --surface, radio 10, alto mínimo 200 px, un icono de trazo (flecha arriba, 20 px, 1.5 px, currentColor), texto 15 y ayuda 13 ("JPEG, PNG o WebP · hasta 10 MB"). Debajo, los cuatro ejemplos: miniaturas 96 × 96 radio 8 con el id en monoespaciada 12 y "ISIC 2020, CC BY-NC".
- Carga: línea de progreso indeterminada de 2 px --accent bajo el encabezado y "Analizando… 0,4 s" en 14 --text-2. Sin spinner.
- Resultado: dos columnas en escritorio (imagen 480 px a la izquierda, resultados a la derecha, `flex-wrap`), apiladas en teléfono. Encima, una línea 14 --text-2 con el id en monoespaciada y el botón secundario "Analizar otra imagen".
  - Tarjeta de probabilidad (borde --border, radio 10, relleno 24): etiqueta 12 mayúsculas --text-2 "Probabilidad calibrada"; número 52/700; al lado "X veces la tasa base (1,6 %)" en 15 --text-2; barra de 10 px radio 999, pista --border, relleno --accent hasta el valor; marcas: umbral = línea sólida 2 px --text, tasa base = línea discontinua 2 px --text, 22 px de alto; rótulos 12 --text-2 ("0,1 %", "umbral", "tasa base", "100 %"); nota "Escala logarítmica" 12. Todos los valores vienen de la API.
  - Tarjeta de recomendación: por encima del umbral, fondo --accent-tint, borde --accent-tint-border, etiqueta 12 mayúsculas --accent-hover "Recomendación", texto 22/600 y segunda línea 15 --text-2. Por debajo, misma tarjeta con fondo --surface y borde --border. Los textos actuales no cambian.
  - Mapa de activación: recorte en tarjeta con borde --border y radio 10; chip arriba a la izquierda "Mapa de activación · recorte de 224 px" (fondo blanco 90 %, 12/500, radio 6); fila de controles: etiqueta 13 + `input type=range` con accent-color --accent + botón secundario de 36 px "Ver sin mapa"; leyenda 13 --text-2 (texto actual).
  - Detalles técnicos: `<details>`/`<summary>` como fila de 14 con fondo --surface, borde --border, radio 10, chevron de trazo; dentro, lista de definiciones 14 y el JSON en `<pre>` monoespaciada 12 con alto máximo 320 px.
- Pie: borde superior --border, fondo --surface, 13 --text-2: a la izquierda el aviso corto y el enlace "Ficha del modelo"; a la derecha "Edgar Eduardo Ontiveros Lara · a335951 · Facultad de Ingeniería, UACH" y eo.svg a 18 px en currentColor.
- Modal de aviso: fondo blanco, radio 12, ancho máximo 520, sombra de modal, título 22/600, cuerpo 15, botón primario "Entiendo".
- Errores: banda en línea con fondo --surface, borde --border, texto 14 e icono de trazo; sin rellenos rojos.
- /modelo: mismo sistema. h1 28/600; h2 18/600 con filete inferior; tablas en 14 con números tabulares alineados a la derecha, cabecera 12 mayúsculas --text-2, solo filetes horizontales; intervalos en --text-2; tabla lado a lado modelo único / ensamble desde `/model-info`; limitaciones como secciones numeradas en 15; atribución con el escudo al final, como hoy.

## F7b.3 — Símbolo y favicon
Símbolo "lente": viewBox 0 0 32 32; anillo `circle cx=16 cy=16 r=11` con trazo 3 y sin relleno; punto `circle cx=19.5 cy=19.5 r=4` relleno. Archivos en `services/web/public/`: `mark.svg` (currentColor, para el encabezado), `favicon.svg` (trazo y punto en --accent sobre transparente; dentro del SVG, `@media (prefers-color-scheme: dark)` cambia a #93B4FF), `favicon.ico` (16 y 32), `apple-touch-icon.png` (180 px, símbolo en --accent sobre blanco con 20 % de margen). Sustituye el favicon.svg actual; eo.svg no se toca. En index.html: `<title>Detección asistida de melanoma</title>`, `<link rel="icon" href="/favicon.svg" type="image/svg+xml">`, `<link rel="icon" href="/favicon.ico" sizes="32x32">`, `<link rel="apple-touch-icon" href="/apple-touch-icon.png">`, `<meta name="theme-color" content="#1D4ED8">`. Los PNG/ICO se generan con un script en `scripts/` a partir del SVG y se commitean.

## F7b.4 — Lo que se elimina
Sombras en tarjetas, degradados, iconos de color o emojis, bordes izquierdos de color, animaciones, títulos centrados tipo portada, más de un acento, radios mezclados, texto de relleno.

## F7b.5 — Pruebas
- `test_web_no_external_requests`: en `services/web/dist` ninguna petición de red a terceros: sin fonts.googleapis/gstatic, sin `<link>`, `<script>`, `@import` ni `url(https://…)` externos; las fuentes están dentro de dist. Los `href` de enlaces del contenido (repositorio, DOI de ISIC, DDI, UACH) sí se permiten.
- `test_web_icons_present`: mark.svg, favicon.svg, favicon.ico y apple-touch-icon.png existen en dist y están referenciados en index.html.
- `test_web_tokens_only`: ningún color hexadecimal en el CSS de componentes fuera de tokens.css.
- Siguen en verde: test_web_no_model_constants, test_limitations_present, test_example_images_are_val_not_ddi, test_api_prefix_and_spa, las pruebas Vitest de formato y recomendación.
- `reports/f7b_visual.md`: tabla de contraste de cada par texto/fondo de los tokens con su razón (todas ≥ 4.5:1, o ≥ 3:1 si el texto es ≥ 24 px) y capturas regeneradas con `make f7-screenshots` (escritorio y teléfono; análisis y /modelo).

## Criterios de aceptación
1. tokens.css con los valores de F7b.1 y `test_web_tokens_only` en verde.
2. Inter empaquetada; `test_web_no_external_requests` en verde; `npm run build` limpio.
3. Pantalla de análisis con los componentes de F7b.2; usable en teléfono en vertical.
4. /modelo con el mismo sistema y la tabla lado a lado.
5. Símbolo, favicon, apple-touch-icon y título según F7b.3.
6. `reports/f7b_visual.md` con contraste y capturas.
7. Pruebas de F7 y las tres nuevas en verde; imagen Docker dentro del límite.
8. `make ci` en verde; push.

## Orden de trabajo
Sesión 1: F7b.1, F7b.3, encabezado, pie, zona de carga, botones. Sesión 2: resultado, /modelo, modal, errores, pruebas, capturas, cierre.

Al cerrar F7b repórtame las capturas (análisis y /modelo, escritorio y teléfono), la tabla de contraste y el estado de las pruebas.

---

## Estado y desviaciones respecto a la spec

Dos sesiones el 2026-10-26 (commits de la sesión 1 y 2).

1. **F7b.1.** `services/web/src/styles/tokens.css` con los diez colores, la escala 12/13/14/15/17/22/52
   (más 18 para h2 y 28 para h1), espacio 4–48, contenedor 1120, radios 10/8/6/999, bordes de
   1 px, sombra solo del modal, movimiento de 150 ms y `prefers-reduced-motion`. Inter variable
   4.1 en subconjunto latín (`pyftsubset`, 100 KB woff2) en `public/fonts/` con su licencia OFL;
   `font-feature-settings: "tnum"` en todo número; fallback system-ui. `test_web_tokens_only`.
2. **F7b.2.** Encabezado de 64 px sin fijar con el símbolo en currentColor; botones de 40 y 36 px
   en tres variantes; zona de carga de 200 px con borde discontinuo e icono de trazo;
   ejemplos de 96 × 96 con id monoespaciado y «ISIC 2020, CC BY-NC»; línea de progreso de 2 px
   bajo el encabezado y «Analizando… 0,4 s» (sin spinner ni esqueleto); resultado en dos
   columnas (imagen 480 px) apiladas en teléfono; tarjetas de probabilidad (52/700, barra con
   umbral sólido y tasa base discontinua, «Escala logarítmica»), recomendación (tinte por encima
   del umbral, textos de F7 intactos), mapa de activación con chip y fila de controles, detalles
   técnicos como `<details>` con chevron y lista de definiciones; pie en dos bloques; modal de
   520 px con la única sombra; errores en banda neutra con icono. `/modelo` con h1 28, h2 18 con
   filete, tablas solo con filetes horizontales, intervalos en `--text-2`, tabla lado a lado y
   limitaciones numeradas. **Desviaciones:** la zona de carga conserva un botón secundario de
   36 px «Seleccionar archivo» (objetivo de toque en teléfono); las miniaturas llevan además la
   etiqueta real («Melanoma confirmado» / «Benigna confirmada»), que la demo necesita para
   mostrar las cuatro celdas; el pie no muestra la versión del modelo (va en la ficha y en los
   detalles técnicos).
3. **F7b.3.** `scripts/f7b_icons.py` (`make f7b-icons`) genera `mark.svg`, `favicon.svg` con
   `prefers-color-scheme: dark`, `favicon.ico` (16 y 32) y `apple-touch-icon.png` (180, 20 % de
   margen) desde el mismo dibujo; `index.html` con el título, los tres iconos y `theme-color`.
   `test_web_icons_present`.
4. **F7b.4.** Sin sombras en tarjetas, sin degradados, sin iconos de color, sin bordes de color,
   sin esqueleto animado, un solo acento. El CAM conserva su mapa de calor (es el dato).
5. **F7b.5.** `test_web_no_external_requests`, `test_web_icons_present`, `test_web_tokens_only`
   en verde junto con las de F7 y las 13 de Vitest. `reports/f7b_visual.md`
   (`make f7b-visual`): 12 pares de contraste, todos ≥ 4.5:1 (mínimo 6.70:1, enlaces sobre
   blanco); capturas regeneradas a 1280 y 390 px.
6. Imagen Docker: 437 MB sin comprimir (límite 650). `make ci` en verde.

Criterios de aceptación: 8/8.

---

## F7b.6 — Ajustes del 2026-10-27: ancho y colores institucionales

### Ancho y escala (escritorio)
- Contenedor de 1360 px con márgenes de 40 px a partir de 1280 px de ancho; por debajo, lo actual (1120/24). Teléfono sin cambios.
- Escala en escritorio: cuerpo 16, UI 15, wordmark 18, recomendación 24, probabilidad 64; botones de 42 px (36 dentro de tarjetas); tarjetas con relleno 28/32; separación entre columnas 32; columna de la imagen 560 px, resultados el resto. Encabezado de 68 px.

### Tokens de color (sustituyen a los actuales en tokens.css)
--accent #0B6E99 (texto de enlaces, botones primarios, etiqueta de la recomendación, símbolo del encabezado, foco) · --accent-hover #085578 · --accent-bright #0A93C6 (solo donde no hay texto: subrayado del menú activo, relleno de la barra, marcas) · --accent-tint #E8F4FA · --accent-tint-border #B8DCEE · --signature #7A2A8A (franja de 4 px por encima del encabezado; en ningún otro sitio). Los demás tokens no cambian. Origen: azul del logo de la Facultad de Ingeniería (#0A93C6, oscurecido a #0B6E99 donde lleva texto para cumplir AA) y morado del escudo de la UACH (#7A2A8A).
- `theme-color` #0B6E99; favicon y apple-touch-icon regenerados con #0B6E99 (modo oscuro #5FB8E6) vía make f7b-icons.
- reports/f7b_visual.md regenerado: todos los pares con texto ≥ 4.5:1 (--accent sobre blanco 5.67:1, blanco sobre --accent 5.67:1, --accent sobre tinte 5.06:1).

### Logos institucionales
- Archivos: `services/web/public/escudo-uach.png` (a partir del escudo-color.png existente) y `services/web/public/facultad-ingenieria.png` (archivo nuevo del autor). A ambos: quitar el fondo blanco (transparente), recortar al contenido, exportar a 2× de la altura máxima de uso (176 px) para que se vean nítidos; conservar los originales en `raw-assets/logos/` fuera del build. Se cambia la regla de F7b que limitaba el escudo a /modelo.
- Pie (fondo --bg, filete superior --border): a la izquierda el aviso corto y «Ficha del modelo»; a la derecha, escudo UACH y logo de la Facultad a 44 px de alto en color, luego dos líneas («Edgar Eduardo Ontiveros Lara · a335951» en --text 500 y «Facultad de Ingeniería · Universidad Autónoma de Chihuahua» en --text-2) y al final el logo EO·. En teléfono los logos van arriba del texto, centrados.
- /modelo, atribución final: los dos logos a 72 px con el mismo texto.
- Logo EO·: restaurar sus colores originales. Están en la primera versión del archivo que el autor copió al repo (git log --follow sobre services/web/public/eo.svg y el favicon.svg que lo precedió); si esa versión ya no tiene color, tomarlo del repositorio edgar-ontiveros.com. Se muestra a 20 px de alto en el pie y a 28 px en /modelo, sin currentColor, con sus colores. Los logos quedan exentos de test_web_tokens_only (son imágenes, no CSS).

### Pruebas y cierre
- test_web_icons_present cubre también escudo-uach.png y facultad-ingenieria.png en dist.
- Las pruebas de F7 y F7b siguen en verde; make f7-screenshots regenerado a 1440 y 390 px; make ci en verde; push.
- Al final, make demo (puerto 8010), déjala corriendo y dame la URL con capturas de análisis, /modelo y el pie en escritorio y teléfono.

### Estado de F7b.6 (2026-10-27)

Hecho. Tokens: `--accent #0b6e99`, `--accent-hover #085578`, `--accent-bright #0a93c6` (subrayado
activo, relleno y marcas de la barra, línea de progreso), `--accent-tint #e8f4fa`,
`--accent-tint-border #b8dcee`, `--signature #7a2a8a` (franja de 4 px sobre el encabezado y nada
más); escala de escritorio por `@media (min-width: 1280px)` en `tokens.css` (contenedor 1360,
márgenes 40, cuerpo 16, UI 15, wordmark 18, recomendación 24, probabilidad 64, botones 42,
tarjetas 28/32, columnas a 32, imagen 560, encabezado 68). Favicons regenerados con #0B6E99
(#5FB8E6 en oscuro); `theme-color` #0B6E99. Contraste (`reports/f7b_visual.md`): 13 pares,
todos ≥ 4.5:1 (`--accent` sobre blanco 5.67:1, blanco sobre `--accent` 5.67:1, `--accent` sobre
tinte 5.06:1). Logos: `scripts/f7b_logos.py` (`raw-assets/logos/` → fondo transparente, recorte,
176 px de alto) produce `escudo-uach.png` y `facultad-ingenieria.png`; el logo de la Facultad es
`uach-ingenieria.png` del repositorio edgar-ontiveros.com (respaldo del autor); `escudo-color.png`
se retira. `Institution.tsx` en el pie (44 px) y en la atribución de `/modelo` (72 px); EO· con
su cian original (#22D3EE, favicon de edgar-ontiveros.com; la primera versión en este repo ya
usaba currentColor) a 20 y 28 px. `test_web_icons_present` cubre los dos logos y `eo.svg`;
capturas a 1440 y 390 px. **Desviación:** el logo de la Facultad no llegó como archivo nuevo; se
tomó del respaldo del sitio personal del autor.
