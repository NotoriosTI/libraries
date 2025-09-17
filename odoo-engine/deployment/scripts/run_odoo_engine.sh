#!/bin/bash

# deployment/scripts/run_odoo_engine.sh

set -e

PROJECT_ID="notorios"
REGION=${1:-"us-central1"}
INSTANCE_NAME="app-temp"

show_usage() {
  echo "Usage: $0 [OPTIONS] [COMMAND]"
  echo "  --region REGION         Specify region (default: us-central1)"
  echo "Commands:"
  echo "  sync      Run synchronization (default)"
  echo "  test      Test connections only"
}

COMMAND="sync"
while [[ $# -gt 0 ]]; do
  case $1 in
    --region) REGION="$2"; shift 2;;
    sync) COMMAND="sync"; shift;;
    test) COMMAND="test"; shift;;
    --help) show_usage; exit 0;;
    *) echo "Unknown option: $1"; show_usage; exit 1;;
  esac
done

echo "🚀 Odoo Engine run ($COMMAND)"

if [ -f "/opt/odoo-engine/.env" ]; then
  echo "📍 Running on VM..."
  cd /opt/odoo-engine
  if [ "$COMMAND" = "test" ]; then
    sudo docker compose --env-file .env -f docker-compose.prod.yml run --rm -T odoo-engine python -c "import sys; print('Testing DB host:', 'localhost'); print('OK')"
  else
    sudo docker compose --env-file .env -f docker-compose.prod.yml up -d odoo-engine && \
    sudo docker compose --env-file .env -f docker-compose.prod.yml logs -f odoo-engine
  fi
  else
    echo "📍 Running locally, connecting to VM..."
    gcloud compute ssh langgraph --zone=us-central1-c --command="
    cd /opt/odoo-engine
    if [ '$COMMAND' = 'test' ]; then
      sudo docker compose --env-file .env -f docker-compose.prod.yml run --rm -T odoo-engine python -c \"print('OK')\" 
    else
      sudo docker compose --env-file .env -f docker-compose.prod.yml up -d odoo-engine && 
      sudo docker compose --env-file .env -f docker-compose.prod.yml logs -f odoo-engine
    fi
  "
fi

echo "✅ Done"

