#!/usr/bin/env bash
# F8 — Preparación de la instancia (Ubuntu LTS): Docker Engine con compose, ufw con 22/80/443 y
# la carpeta de despliegue. Idempotente: se puede correr varias veces. Uso en la instancia:
#   sudo bash install.sh
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "ejecutar como root: sudo bash install.sh" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q ca-certificates curl gnupg ufw

if ! command -v docker >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -q
  apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi
systemctl enable --now docker
usermod -aG docker ubuntu || true

ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw --force enable

install -d -o ubuntu -g ubuntu /opt/melanoma /opt/melanoma/bundle
docker --version
docker compose version
echo "instancia lista: copiar deploy/docker-compose.yml y deploy/Caddyfile a /opt/melanoma y el paquete a /opt/melanoma/bundle"
