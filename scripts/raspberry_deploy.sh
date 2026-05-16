#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/vse-manager}"
BACKEND_DIR="$APP_DIR/apps/backend"
FRONTEND_DIR="$APP_DIR/apps/frontend"

cd "$APP_DIR"

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "==> Aggiorno sorgenti"
  git pull --ff-only
else
  echo "==> Directory non git: salto git pull"
fi

echo "==> Backend dependencies"
"$BACKEND_DIR/.venv/bin/pip" install -r "$BACKEND_DIR/requirements.txt"

echo "==> Frontend dependencies e build"
npm --prefix "$FRONTEND_DIR" install
npm --prefix "$FRONTEND_DIR" run build

echo "==> Migration database"
cd "$BACKEND_DIR"
.venv/bin/alembic upgrade head

echo "==> Riavvio servizi"
sudo systemctl restart vse-manager-backend
sudo systemctl reload nginx

echo "Deploy completato."
sudo systemctl --no-pager --lines=0 status vse-manager-backend
