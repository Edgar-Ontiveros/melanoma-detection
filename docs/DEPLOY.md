# Despliegue (F8)

La demostración principal para el examen corre en la laptop (`make demo`, `docs/DEMO.md`). El
despliegue en internet es el respaldo y la evidencia de que el sistema corre fuera de ella.

## Arquitectura

- **Imagen:** `ghcr.io/edgar-ontiveros/melanoma-detection`, publicada por el CI en cada push a
  `main` que pase todas las comprobaciones (job `publish` de `.github/workflows/ci.yml`), con
  las etiquetas `<sha corto>` y `latest`. El servidor solo hace `docker compose pull`; nunca
  compila. **Pendiente del autor (una vez):** en GitHub → perfil → Packages →
  `melanoma-detection` → Package settings → *Change visibility* → Public. Sin eso, el `pull`
  en la instancia pediría credenciales.
- **Paquete de modelo:** el tar.gz del release `model-28a90b4-4264e888`, descargado y
  verificado por SHA256 en la instancia, montado en `/bundle` (solo lectura).
- **Instancia:** AWS Lightsail, Ubuntu LTS, 2 GB de RAM, 1 vCPU, 60 GB SSD, región
  `us-east-1`, IP estática. Costo fijo ≈ 12 USD/mes (plan de 12 USD; la IP estática es gratis
  mientras esté asociada a una instancia). Puertos abiertos: 80 y 443 para todos, 22 solo desde
  la IP del autor.
- **TLS y proxy:** Caddy 2 con certificados de Let's Encrypt para `melanoma.edgar-ontiveros.com`
  (registro A en Cloudflare en modo solo DNS, sin proxy). `deploy/Caddyfile`: cuerpo máximo
  10 MB, encabezados de seguridad, logs JSON rotados.
- **Sin estado:** nada se almacena; sin base de datos; sin credenciales en el repositorio. Las
  imágenes se procesan en memoria.

## Pasos de la primera vez

1. **Perfil de AWS.** La fase usa el perfil `personal` de la CLI, distinto de los perfiles de la
   empresa (`default`, `mfa`, `edgar-mfa`). Crearlo con credenciales de la cuenta personal:
   ```bash
   aws configure --profile personal        # access key, secret, región us-east-1, salida json
   aws sts get-caller-identity --profile personal   # debe mostrar la cuenta personal
   ```
2. **Instancia e IP estática** (se ejecuta solo después del «sí» del autor al ver los recursos y
   el costo):
   ```bash
   P="--profile personal --region us-east-1"
   aws lightsail create-key-pair $P --key-pair-name melanoma --query privateKeyBase64 --output text > ~/.ssh/lightsail-melanoma.pem && chmod 600 ~/.ssh/lightsail-melanoma.pem
   aws lightsail create-instances $P --instance-names melanoma --availability-zone us-east-1a --blueprint-id ubuntu_24_04 --bundle-id small_3_0 --key-pair-name melanoma
   aws lightsail allocate-static-ip $P --static-ip-name melanoma-ip
   aws lightsail attach-static-ip $P --static-ip-name melanoma-ip --instance-name melanoma
   aws lightsail put-instance-public-ports $P --instance-name melanoma --port-infos \
     fromPort=80,toPort=80,protocol=tcp fromPort=443,toPort=443,protocol=tcp fromPort=443,toPort=443,protocol=udp \
     fromPort=22,toPort=22,protocol=tcp,cidrs=<IP del autor>/32
   aws lightsail get-static-ip $P --static-ip-name melanoma-ip --query staticIp.ipAddress --output text
   ```
3. **DNS.** El autor crea en Cloudflare el registro `A melanoma → <IP estática>`, **solo DNS**
   (nube gris). Comprobar: `dig +short melanoma.edgar-ontiveros.com` debe devolver la IP.
4. **Instalar y arrancar** desde la laptop (SSH con la llave del paso 2):
   ```bash
   make deploy-install DEPLOY_HOST=ubuntu@<IP>     # Docker, ufw, compose, Caddyfile y el paquete del release
   make deploy DEPLOY_HOST=ubuntu@<IP>             # pull de la imagen y up -d; Caddy pide el certificado
   ```
5. **Verificar:** `curl https://melanoma.edgar-ontiveros.com/api/health`; una predicción con una
   imagen de ejemplo (validación, nunca test):
   `curl -F "file=@services/web/public/examples/ISIC_5037784.jpg" https://melanoma.edgar-ontiveros.com/api/predict`;
   latencia remota con `uv run python scripts/bench_api.py --url https://melanoma.edgar-ontiveros.com --n 50 --out reports/f8_latency.md --title "F8 — Latencia remota"`;
   la interfaz en el teléfono y `/modelo`.

## Actualizar

Cada push a `main` publica una imagen nueva. En la instancia:

```bash
make deploy                       # latest
make deploy MELANOMA_TAG=<sha>    # una versión concreta
```

`make deploy` es idempotente: copia compose y Caddyfile, escribe `.env`, hace `pull` y
`up -d --remove-orphans`. Para cambiar de paquete de modelo: `make deploy-install
BUNDLE_RELEASE=model-<git>-<sha8>` (vuelve a bajar y verificar el tar.gz) y después `make deploy`.

## Apagar y encender

- Solo los contenedores: `make deploy-stop` / `make deploy-start` (la instancia sigue costando).
- La instancia (deja de cobrar el cómputo; la IP estática desasociada cuesta 0.005 USD/h):
  ```bash
  aws lightsail stop-instance --profile personal --region us-east-1 --instance-name melanoma
  aws lightsail start-instance --profile personal --region us-east-1 --instance-name melanoma
  ```
- Borrar todo al terminar: `delete-instance`, `release-static-ip`, borrar el registro A.

## Costo mensual estimado

| Concepto | USD/mes |
|---|---:|
| Lightsail `small_3_0` (2 GB RAM, 1 vCPU, 60 GB, 3 TB de transferencia) | 12.00 |
| IP estática asociada | 0.00 |
| Dominio y DNS en Cloudflare (ya contratados) | 0.00 |
| Certificado (Let's Encrypt) | 0.00 |
| **Total** | **≈ 12.00** |

## Estado

| Paso | Estado |
|---|---|
| F8.1 job `publish` en el CI | hecho (se activa en el siguiente push a `main`); visibilidad pública del paquete pendiente del autor |
| F8.2 `deploy/` y objetivos de Makefile | hecho |
| F8.3 instancia, IP, puertos | **detenido**: no existe el perfil `personal` de la CLI (pausa obligatoria a) |
| DNS en Cloudflare | pendiente del autor, después de la IP |
| F8.4 verificación remota y latencia | pendiente |
