#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/vse-manager}"
APP_USER="${APP_USER:-pi}"
APP_GROUP="${APP_GROUP:-$APP_USER}"
BACKEND_DIR="$APP_DIR/apps/backend"
FRONTEND_DIR="$APP_DIR/apps/frontend"

if [[ ! -d "$APP_DIR" ]]; then
  echo "Directory app non trovata: $APP_DIR"
  echo "Copia o clona prima il progetto in $APP_DIR."
  exit 1
fi

if [[ "$EUID" -ne 0 ]]; then
  echo "Esegui con sudo: sudo APP_USER=$APP_USER bash scripts/raspberry_install.sh"
  exit 1
fi

echo "==> Pacchetti di sistema"
apt-get update
apt-get install -y python3 python3-venv python3-pip nodejs npm nginx postgresql postgresql-contrib

echo "==> Permessi progetto"
chown -R "$APP_USER:$APP_GROUP" "$APP_DIR"

echo "==> Virtualenv backend"
sudo -u "$APP_USER" python3 -m venv "$BACKEND_DIR/.venv"
sudo -u "$APP_USER" "$BACKEND_DIR/.venv/bin/pip" install --upgrade pip
sudo -u "$APP_USER" "$BACKEND_DIR/.venv/bin/pip" install -r "$BACKEND_DIR/requirements.txt"

if [[ ! -f "$BACKEND_DIR/.env" ]]; then
  echo "==> Creo .env da .env.example"
  sudo -u "$APP_USER" cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
  echo "Configura $BACKEND_DIR/.env prima di usare l'app in produzione."
fi

echo "==> Frontend"
sudo -u "$APP_USER" npm --prefix "$FRONTEND_DIR" install
sudo -u "$APP_USER" npm --prefix "$FRONTEND_DIR" run build

echo "==> Migration database"
sudo -u "$APP_USER" bash -lc "cd '$BACKEND_DIR' && .venv/bin/alembic upgrade head"

echo "==> Nginx"
cp "$APP_DIR/deploy/nginx/vse-manager.conf" /etc/nginx/sites-available/vse-manager.conf
ln -sfn /etc/nginx/sites-available/vse-manager.conf /etc/nginx/sites-enabled/vse-manager.conf
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx
systemctl reload nginx

echo "==> Servizio backend"
sed \
  -e "s|^User=.*|User=$APP_USER|" \
  -e "s|^Group=.*|Group=$APP_GROUP|" \
  -e "s|/opt/vse-manager|$APP_DIR|g" \
  "$APP_DIR/deploy/systemd/vse-manager-backend.service" > /etc/systemd/system/vse-manager-backend.service

systemctl daemon-reload
systemctl enable vse-manager-backend
systemctl restart vse-manager-backend

echo "Installazione completata."
echo "Stato backend: sudo systemctl status vse-manager-backend"
echo "Log backend:   sudo journalctl -u vse-manager-backend -f"
