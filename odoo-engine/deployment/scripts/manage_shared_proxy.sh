#!/bin/bash

# deployment/scripts/manage_shared_proxy.sh

set -e

PROJECT_ID="notorios"
REGION=${1:-"us-central1"}
INSTANCE_NAME="app-temp"

show_usage() {
  echo "Usage: $0 [start|stop|restart|status|logs|help] [--region REGION]"
}

COMMAND=""
while [[ $# -gt 0 ]]; do
  case $1 in
    start|stop|restart|status|logs|help) COMMAND="$1"; shift;;
    --region) REGION="$2"; shift 2;;
    *) echo "Unknown option: $1"; show_usage; exit 1;;
  esac
done

if [ -z "$COMMAND" ] || [ "$COMMAND" = "help" ]; then show_usage; exit 0; fi

if [ -f "/opt/odoo-engine/.env" ]; then
  echo "📍 Running on VM..."
  cd /opt/odoo-engine
  case $COMMAND in
    start) sudo docker-compose --env-file .env -f docker-compose.shared-proxy.yml up -d;;
    stop) sudo docker-compose --env-file .env -f docker-compose.shared-proxy.yml down;;
    restart) sudo docker-compose --env-file .env -f docker-compose.shared-proxy.yml restart;;
    status) sudo docker-compose --env-file .env -f docker-compose.shared-proxy.yml ps;;
    logs) sudo docker-compose --env-file .env -f docker-compose.shared-proxy.yml logs -f;;
  esac
else
  echo "📍 Running locally, connecting to VM..."
  case $COMMAND in
    start)
      gcloud compute ssh langgraph --zone=us-central1-c --command="cd /opt/odoo-engine && sudo docker-compose --env-file .env -f docker-compose.shared-proxy.yml up -d";;
    stop)
      gcloud compute ssh langgraph --zone=us-central1-c --command="cd /opt/odoo-engine && sudo docker-compose --env-file .env -f docker-compose.shared-proxy.yml down";;
    restart)
      gcloud compute ssh langgraph --zone=us-central1-c --command="cd /opt/odoo-engine && sudo docker-compose --env-file .env -f docker-compose.shared-proxy.yml restart";;
    status)
      gcloud compute ssh langgraph --zone=us-central1-c --command="cd /opt/odoo-engine && sudo docker-compose --env-file .env -f docker-compose.shared-proxy.yml ps";;
    logs)
      gcloud compute ssh langgraph --zone=us-central1-c --command="cd /opt/odoo-engine && sudo docker-compose --env-file .env -f docker-compose.shared-proxy.yml logs -f";;
  esac
fi

echo "✅ Shared proxy management completed!"

