# Demo local para el examen

La demostración principal corre en la laptop, en Docker, con la misma imagen que construye el
CI y el paquete de modelo real montado. El despliegue en internet (F8) es el respaldo.

## Levantar la demo (un comando)

```bash
make demo              # construye la imagen, la levanta en http://127.0.0.1:8010 y espera a /api/health
make demo PORT=8020    # si el 8010 estuviera ocupado
```

Requisitos: Docker Desktop encendido con la integración de WSL activa y `models/bundle/` con el
paquete del ensamble (`make export-bundle`, o el tar.gz del release `model-28a90b4-4264e888`
descomprimido ahí). El puerto 8000 lo usa otro servicio de la laptop; por eso la demo va en 8010.
El contenedor se llama `melanoma-demo`; si ya existe uno con ese nombre, `make demo` lo reemplaza.

Abrir en el navegador:

- **Análisis:** <http://127.0.0.1:8010>
- **Ficha del modelo:** <http://127.0.0.1:8010/modelo>

## Qué mostrar

1. El aviso de uso (modal) y el pie: herramienta de apoyo, no diagnóstico.
2. Las cuatro imágenes de ejemplo (validación, ISIC 2020, CC BY-NC), que cubren las cuatro
   celdas de la matriz de confusión; la etiqueta real es visible al elegirlas:
   - `ISIC_5037784`: melanoma referido (verdadero positivo).
   - `ISIC_5733748`: melanoma **no** referido (falso negativo): el sistema no es infalible.
   - `ISIC_1265382`: benigna no referida (verdadero negativo).
   - `ISIC_7330819`: benigna referida (falso positivo): el precio de la alta sensibilidad.
   Para cada una: probabilidad calibrada con la tasa base, recomendación, mapa de activación
   (con «Ver sin mapa») y los detalles técnicos plegados.
3. `/modelo`: qué es y qué no es; la tabla lado a lado del modelo único (F4) y el ensamble
   (F4b) con intervalos; cómo leer la probabilidad; las nueve limitaciones; datos y licencias;
   versión del paquete y miembros del ensamble.
4. Si preguntan por la API: <http://127.0.0.1:8010/api/docs> (OpenAPI) y
   `curl http://127.0.0.1:8010/api/model-info`.

## Verificación rápida antes del examen

```bash
curl -s http://127.0.0.1:8010/api/health
curl -s http://127.0.0.1:8010/api/model-info | python3 -c "import json,sys; i=json.load(sys.stdin); print(i['ensemble'], i['model_version'])"
curl -s -F "file=@services/web/public/examples/ISIC_5037784.jpg" http://127.0.0.1:8010/api/predict | python3 -c "import json,sys; b=json.load(sys.stdin); print(b['probability'], b['refer'], b['cam']['status'], b['latency_ms'], 'ms')"
```

Latencia medida dentro del contenedor el 2026-10-26: unos 100–150 ms por predicción (tres
modelos ONNX en CPU) y 0,3–0,5 s de ida y vuelta desde el navegador la primera vez.

## Apagar

```bash
make demo-stop
```

## Plan B sin Docker

Si Docker no arranca, la API y la interfaz corren directo con `uv` (necesita `make setup`
hecho y `services/web/dist` construido con `make web-build`):

```bash
make web-build   # una vez; genera services/web/dist
make api         # uvicorn en http://127.0.0.1:8000 con MODEL_BUNDLE_DIR=models/bundle
```

Si el 8000 está ocupado:

```bash
MODEL_BUNDLE_DIR=models/bundle uv run --no-sync uvicorn services.api.main:app --host 127.0.0.1 --port 8010
```

Es el mismo código y el mismo paquete; solo cambia que corre en el entorno de `uv` en vez de en
el contenedor.

## Abrirla desde el teléfono (misma red Wi-Fi)

La demo escucha solo en `127.0.0.1` de WSL2. Para verla desde el teléfono hay que exponerla en
Windows; son pasos de configuración que **no se ejecutan automáticamente**:

1. Levantar la demo escuchando en todas las interfaces de WSL:
   `docker run -d --name melanoma-demo -p 0.0.0.0:8010:8000 -v "$PWD/models/bundle:/bundle:ro" melanoma-api`
   (o cambiar `127.0.0.1:$(DEMO_PORT)` por `0.0.0.0:$(DEMO_PORT)` en el objetivo `demo` del Makefile).
2. En PowerShell como administrador, reenviar el puerto de Windows a WSL (la IP de WSL cambia
   al reiniciar; `wsl hostname -I` la muestra):
   ```powershell
   netsh interface portproxy add v4tov4 listenport=8010 listenaddress=0.0.0.0 connectport=8010 connectaddress=$(wsl hostname -I).Trim()
   New-NetFirewallRule -DisplayName "melanoma-demo 8010" -Direction Inbound -Protocol TCP -LocalPort 8010 -Action Allow
   ```
   Con Windows 11 y `networkingMode=mirrored` en `.wslconfig` el portproxy no hace falta; basta la
   regla del firewall.
3. En el teléfono, abrir `http://<IP de la laptop en la red>:8010` (`ipconfig` en Windows).
4. Al terminar: `netsh interface portproxy delete v4tov4 listenport=8010 listenaddress=0.0.0.0`
   y borrar la regla del firewall.

Sin HTTPS la cámara del navegador móvil no está disponible, pero subir una foto de la galería sí
funciona.
