#!/bin/bash

# deployment/scripts/deploy.sh
# Deployment Script for Odoo Engine (modeled after Product Engine)

set -e

# Optional flags
SKIP_PREREQUISITES=false
SKIP_SECRETS=false
SKIP_CONNECTION_CHECK=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-prerequisites) SKIP_PREREQUISITES=true; shift;;
        --skip-secrets) SKIP_SECRETS=true; shift;;
        --skip-connection-check) SKIP_CONNECTION_CHECK=true; shift;;
        --skip-checks)
            SKIP_PREREQUISITES=true; SKIP_SECRETS=true; SKIP_CONNECTION_CHECK=true; shift;;
        *) shift;;
    esac
done

PROJECT_ID="notorios"
REGION=${REGION:-"us-central1"}
ZONE=${ZONE:-"us-central1-c"}
VM_NAME="langgraph"
IMAGE_NAME="gcr.io/$PROJECT_ID/odoo-engine"
VERSION=${VERSION:-$(date +%Y%m%d-%H%M%S)}
INSTANCE_NAME="app-temp"

echo "🚀 Deploying Odoo Engine"
echo "Project: $PROJECT_ID"
echo "VM: $VM_NAME"
echo "Region: $REGION"
echo "Zone: $ZONE"
echo "Image: $IMAGE_NAME:$VERSION"
echo "Cloud SQL Instance: $INSTANCE_NAME"

check_prerequisites() {
  if [ "$SKIP_PREREQUISITES" = true ]; then echo "⏭️  Skipping prerequisites"; return 0; fi
  command -v gcloud >/dev/null || { echo "gcloud not installed"; exit 1; }
  gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n1 >/dev/null || { echo "Not authenticated"; exit 1; }
  CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null)
  if [ "$CURRENT_PROJECT" != "$PROJECT_ID" ]; then gcloud config set project $PROJECT_ID; fi
  gcloud compute instances describe $VM_NAME --zone=$ZONE >/dev/null || { echo "VM '$VM_NAME' not found"; exit 1; }
  command -v docker >/dev/null || { echo "Docker not installed"; exit 1; }
  docker info >/dev/null || { echo "Docker daemon not running"; exit 1; }
}

verify_secrets() {
  if [ "$SKIP_SECRETS" = true ]; then echo "⏭️  Skipping secrets verification"; return 0; fi
  REQUIRED_SECRETS=(
    "ODOO_PROD_URL" "ODOO_PROD_DB" "ODOO_PROD_USERNAME" "ODOO_PROD_PASSWORD"
    "DB_HOST" "DB_PORT" "DB_NAME" "DB_USER" "DB_PASSWORD"
    "OPENAI_API_KEY"
  )
  missing=()
  for s in "${REQUIRED_SECRETS[@]}"; do
    if ! gcloud secrets describe "$s" >/dev/null 2>&1; then missing+=("$s"); fi
  done
  if [ ${#missing[@]} -ne 0 ]; then
    echo "❌ Missing secrets:"; for m in "${missing[@]}"; do echo "  - $m"; done; exit 1
  fi
}

setup_vm_environment() {
  gcloud compute ssh $VM_NAME --zone=$ZONE --command="
    sudo mkdir -p /opt/odoo-engine && sudo chown \$(whoami):\$(whoami) /opt/odoo-engine
    if ! groups \$(whoami) | grep -q docker; then sudo usermod -aG docker \$(whoami) 2>/dev/null || true; fi
  "
}

check_prerequisites
verify_secrets

echo "🐳 Building Docker image for linux/amd64..."
gcloud auth configure-docker gcr.io --quiet
docker build --platform linux/amd64 -f deployment/Dockerfile -t $IMAGE_NAME:$VERSION -t $IMAGE_NAME:latest .
echo "📤 Pushing to Container Registry..."
docker push $IMAGE_NAME:$VERSION
docker push $IMAGE_NAME:latest

setup_vm_environment

echo "🚚 Deploying to VM..."
gcloud compute scp deployment/docker-compose.prod.yml deployment/docker-compose.shared-proxy.yml deployment/scripts/run_odoo_engine.sh $VM_NAME:/opt/odoo-engine/ --zone=$ZONE

gcloud compute ssh $VM_NAME --zone=$ZONE --command="
  cd /opt/odoo-engine
  gcloud auth configure-docker gcr.io --quiet
  sudo gcloud auth configure-docker gcr.io --quiet
  chmod +x run_odoo_engine.sh
  cat > .env << EOF
PROJECT_ID=$PROJECT_ID
REGION=$REGION
INSTANCE_NAME=$INSTANCE_NAME
ENVIRONMENT=production
EOF
  echo 'Ensuring shared Cloud SQL proxy...'
  sudo docker-compose --env-file .env -f docker-compose.shared-proxy.yml up -d
  echo 'Starting odoo-engine once for verification...'
  sudo docker-compose --env-file .env -f docker-compose.prod.yml up -d
  sleep 5
  sudo docker ps -a --format 'table {{.Names}}\t{{.Status}}' | grep odoo-engine-prod || (echo 'Container failed' && exit 1)
"

echo "⏰ Setting up systemd timer..."
gcloud compute ssh $VM_NAME --zone=$ZONE --command="
  sudo tee /etc/systemd/system/odoo-engine.service > /dev/null << 'EOF'
[Unit]
Description=Odoo Engine Sync Runner
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
WorkingDirectory=/opt/odoo-engine
Environment=PROJECT_ID=$PROJECT_ID
Environment=REGION=$REGION
Environment=INSTANCE_NAME=$INSTANCE_NAME
ExecStart=/usr/bin/sudo /opt/odoo-engine/run_odoo_engine.sh

[Install]
WantedBy=multi-user.target
EOF

  sudo tee /etc/systemd/system/odoo-engine.timer > /dev/null << 'EOF'
[Unit]
Description=Run Odoo Engine every 6 hours
Requires=odoo-engine.service

[Timer]
OnCalendar=*-*-* 00,06,12,18:00:00
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
EOF

  sudo systemctl daemon-reload
  sudo systemctl enable odoo-engine.timer
  sudo systemctl start odoo-engine.timer
"

if [ "$SKIP_CONNECTION_CHECK" = true ]; then
  echo "⏭️  Skipping connection tests"
else
  echo "🧪 Testing connection run..."
  gcloud compute ssh $VM_NAME --zone=$ZONE --command="cd /opt/odoo-engine && timeout 60s sudo ./run_odoo_engine.sh test || true"
fi

echo "Ejecutando sincronización inmediatamente después del deploy..."
gcloud compute ssh $VM_NAME --zone=$ZONE --command="cd /opt/odoo-engine && sudo docker-compose --env-file .env -f docker-compose.prod.yml up odoo-engine"

echo "🛑 Stopping verification container (keeping logs)..."
gcloud compute ssh $VM_NAME --zone=$ZONE --command="cd /opt/odoo-engine && sudo docker stop odoo-engine-prod 2>/dev/null || true"

echo "✅ Deployment completed!"

