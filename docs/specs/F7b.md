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
