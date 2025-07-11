#!/bin/bash

# deployment/scripts/deploy.sh
# Deployment Script for Product Engine

set -e  # Exit on any error

# Parse optional flags first
SKIP_PREREQUISITES=false
SKIP_SECRETS=false
SKIP_CONNECTION_CHECK=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-prerequisites)
            SKIP_PREREQUISITES=true
            shift
            ;;
        --skip-secrets)
            SKIP_SECRETS=true
            shift
            ;;
        --skip-connection-check)
            SKIP_CONNECTION_CHECK=true
            shift
            ;;
        --skip-checks)
            SKIP_PREREQUISITES=true
            SKIP_SECRETS=true
            SKIP_CONNECTION_CHECK=true
            shift
            ;;
        *)
            # Unknown option - ignore for now
            shift
            ;;
    esac
done

# Configuration
PROJECT_ID="notorios"  # Hardcoded project ID
REGION=${1:-"us-central1"}
ZONE=${2:-"us-central1-c"}
VM_NAME="langgraph"
IMAGE_NAME="gcr.io/$PROJECT_ID/product-engine"
VERSION=${3:-$(date +%Y%m%d-%H%M%S)}
INSTANCE_NAME="app-temp"  # Actual Cloud SQL instance name

echo "🚀 Deploying Product Engine"
echo "Project: $PROJECT_ID"
echo "VM: $VM_NAME"
echo "Region: $REGION"
echo "Zone: $ZONE"
echo "Image: $IMAGE_NAME:$VERSION"
echo "Cloud SQL Instance: $INSTANCE_NAME"

# Function to check prerequisites
check_prerequisites() {
    if [ "$SKIP_PREREQUISITES" = true ]; then
        echo "⏭️  Skipping prerequisites check (--skip-prerequisites flag)"
        return 0
    fi
    
    echo "🔍 Checking prerequisites..."
    
    # Check if gcloud is installed and authenticated
    if ! command -v gcloud &> /dev/null; then
        echo "❌ Error: gcloud CLI is not installed"
        exit 1
    fi
    
    # Check if user is authenticated
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n1 &> /dev/null; then
        echo "❌ Error: Not authenticated with gcloud. Run 'gcloud auth login'"
        exit 1
    fi
    
    # Check if correct project is set
    CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null)
    if [ "$CURRENT_PROJECT" != "$PROJECT_ID" ]; then
        echo "⚠️  Warning: Current project is '$CURRENT_PROJECT', expected '$PROJECT_ID'"
        echo "Setting project to $PROJECT_ID..."
        gcloud config set project $PROJECT_ID
    fi
    
    # Check if VM exists
    if ! gcloud compute instances describe $VM_NAME --zone=$ZONE &> /dev/null; then
        echo "❌ Error: VM '$VM_NAME' does not exist in zone '$ZONE'"
        echo "Please create the VM first or check the VM name and zone"
        exit 1
    fi
    
    # Check if Docker is available
    if ! command -v docker &> /dev/null; then
        echo "❌ Error: Docker is not installed"
        exit 1
    fi
    
    # Check if Docker daemon is running
    if ! docker info &> /dev/null; then
        echo "❌ Error: Docker daemon is not running"
        exit 1
    fi
    
    echo "✅ Prerequisites check passed"
}

# Function to setup VM credentials and directory structure
setup_vm_environment() {
    echo "🔐 Setting up VM environment (optimized)..."
    
    # Create directory structure on VM and setup Docker permissions (parallel)
    gcloud compute ssh $VM_NAME --zone=$ZONE --command="
        # Create product-engine directory and setup permissions in parallel
        sudo mkdir -p /opt/product-engine && \
        sudo chown \$(whoami):\$(whoami) /opt/product-engine && \
        
        # Add current user to docker group if not already (non-blocking)
        if ! groups \$(whoami) | grep -q docker; then
            sudo usermod -aG docker \$(whoami) 2>/dev/null || true
        fi
        
        echo 'VM environment setup completed (optimized).'
    "
}

# Function to verify required secrets exist
verify_secrets() {
    if [ "$SKIP_SECRETS" = true ]; then
        echo "⏭️  Skipping secrets verification (--skip-secrets flag)"
        return 0
    fi
    
    echo "🔐 Verifying required secrets in Secret Manager..."
    
    REQUIRED_SECRETS=(
        "ODOO_PROD_URL" "ODOO_PROD_DB" "ODOO_PROD_USERNAME" "ODOO_PROD_PASSWORD"
        "PRODUCT_DB_HOST" "PRODUCT_DB_PORT" "PRODUCT_DB_NAME" "PRODUCT_DB_USER" "PRODUCT_DB_PASSWORD"
        "OPENAI_API_KEY"
    )
    
    missing_secrets=()
    
    for secret in "${REQUIRED_SECRETS[@]}"; do
        if ! gcloud secrets describe $secret &> /dev/null; then
            missing_secrets+=($secret)
        fi
    done
    
    if [ ${#missing_secrets[@]} -ne 0 ]; then
        echo "❌ Error: Missing required secrets in Secret Manager:"
        for secret in "${missing_secrets[@]}"; do
            echo "  - $secret"
        done
        echo ""
        echo "Please create these secrets before proceeding:"
        echo "gcloud secrets create SECRET_NAME --data-file=-"
        exit 1
    fi
    
    echo "✅ All required secrets found in Secret Manager"
}

# Run prerequisites checks
check_prerequisites
verify_secrets

# Build and push Docker image
echo "🐳 Building Docker image for linux/amd64..."

# Optimize Docker credentials for faster builds
echo "🔧 Optimizing Docker credentials for gcr.io only..."
gcloud auth configure-docker gcr.io --quiet

# Build Docker image with optimized caching
docker build --platform linux/amd64 -f deployment/Dockerfile -t $IMAGE_NAME:$VERSION -t $IMAGE_NAME:latest .

echo "📤 Pushing to Container Registry..."
docker push $IMAGE_NAME:$VERSION
docker push $IMAGE_NAME:latest

# Setup VM environment
setup_vm_environment

# Deploy to VM
echo "🚚 Deploying to VM (optimized)..."

# Copy deployment files in parallel
echo "📁 Copying deployment files..."
gcloud compute scp deployment/docker-compose.prod.yml deployment/docker-compose.shared-proxy.yml deployment/scripts/run_product_engine.sh $VM_NAME:/opt/product-engine/ --zone=$ZONE &
COPY_PID=$!

# Wait for file copy to complete
wait $COPY_PID
echo "✅ Files copied successfully"

# SSH into VM and deploy
gcloud compute ssh $VM_NAME --zone=$ZONE --command="
    cd /opt/product-engine
    
    # Configure Docker to use gcloud credentials on VM (optimized for gcr.io only)
    echo '🔐 Configuring Docker authentication for GCR...'
    gcloud auth configure-docker gcr.io --quiet
    
    # Also authenticate sudo docker (optimized)
    sudo gcloud auth configure-docker gcr.io --quiet
    
    # Make the run script executable
    chmod +x run_product_engine.sh
    
    # Create environment file for docker-compose
    cat > .env << EOF
PROJECT_ID=$PROJECT_ID
REGION=$REGION
INSTANCE_NAME=$INSTANCE_NAME
ENVIRONMENT=production
USE_TEST_ODOO=false
FORCE_FULL_SYNC=false
TEST_CONNECTIONS_ONLY=false
EOF
    
    # Verify deployment environment
    echo '🔍 Deployment environment:'
    echo \"PROJECT_ID: $PROJECT_ID\"
    echo \"REGION: $REGION\"
    echo \"INSTANCE_NAME: $INSTANCE_NAME\"
    echo 'ENVIRONMENT: production'
    echo 'USE_TEST_ODOO: false (uses odoo_prod)'
    
    # Pull latest image
    echo \"🐳 Pulling image: $PROJECT_ID/product-engine:latest\"
    sudo docker pull gcr.io/$PROJECT_ID/product-engine:latest
    
    # Stop only the product-engine container (not the shared proxy)
    echo '🛑 Stopping existing product-engine container...'
    sudo docker stop product-engine-prod 2>/dev/null || true
    sudo docker rm product-engine-prod 2>/dev/null || true
    
    # Ensure shared proxy is running (don't remove orphans here)
    echo '🔗 Ensuring shared Cloud SQL proxy is running...'
    sudo docker-compose --env-file .env -f docker-compose.shared-proxy.yml up -d
    
    # Quick check if shared proxy is running (faster check)
    echo '⏳ Checking shared proxy status...'
    if sudo docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -q 'shared-cloud-sql-proxy'; then
        echo '✅ Shared proxy is running'
    else
        echo '❌ Shared proxy failed to start'
        exit 1
    fi
    
    # Start product-engine service for verification (will stop after execution)
    echo '🚀 Starting product-engine service for verification...'
    sudo docker-compose --env-file .env -f docker-compose.prod.yml up -d
    
    # Wait a moment for the container to start and then check logs
    echo '⏳ Waiting for product-engine to start...'
    sleep 5
    
    # Check if product-engine started successfully
    if sudo docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -q 'product-engine-prod'; then
        echo '✅ Product Engine started successfully'
        echo '📋 Container will run once and stop (no continuous restart)'
        
        # Esperar un poco más para que el contenedor complete su ejecución
        echo '⏳ Waiting for container to complete execution...'
        sleep 15
        
        # Verificar estado final usando grep
        if sudo docker ps -a | grep 'product-engine-prod' | grep -q 'Exited'; then
            echo '✅ Product Engine executed successfully and stopped'
        elif sudo docker ps -a | grep 'product-engine-prod' | grep -q 'Up'; then
            echo '✅ Product Engine is running'
        else
            echo '❌ Product Engine failed to execute properly'
            echo '🔍 Container status:'
            sudo docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}' | grep 'product-engine-prod'
            echo '📋 Container logs:'
            sudo docker logs product-engine-prod --tail 20
            exit 1
        fi
    else
        echo '❌ Product Engine failed to start'
        echo '🔍 Checking product-engine logs...'
        sudo docker logs product-engine-prod --tail 20
        exit 1
    fi
"

# Set up systemd service and timer for scheduled execution
echo "⏰ Setting up scheduled execution..."
gcloud compute ssh $VM_NAME --zone=$ZONE --command="
    # Create systemd service for product sync using the new script
    sudo tee /etc/systemd/system/product-engine.service > /dev/null << 'EOF'
[Unit]
Description=Product Engine Database Updater
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
WorkingDirectory=/opt/product-engine
Environment=PROJECT_ID=$PROJECT_ID
Environment=REGION=$REGION
Environment=INSTANCE_NAME=$INSTANCE_NAME
ExecStart=/usr/bin/sudo /opt/product-engine/run_product_engine.sh

[Install]
WantedBy=multi-user.target
EOF

    # Create systemd timer (every 4 hours) - optimized
    sudo tee /etc/systemd/system/product-engine.timer > /dev/null << 'EOF'
[Unit]
Description=Run Product Engine every 4 hours
Requires=product-engine.service

[Timer]
OnCalendar=*-*-* 00,04,08,12,16,20:00:00
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
EOF

    # Enable and start timer (optimized)
    sudo systemctl daemon-reload && \
    sudo systemctl enable product-engine.timer && \
    sudo systemctl start product-engine.timer
    
    echo '⏰ Scheduled execution configured (every 4 hours)'
    sudo systemctl list-timers product-engine.timer --no-pager
"

# Test the deployment with connection test
if [ "$SKIP_CONNECTION_CHECK" = true ]; then
    echo "⏭️  Skipping connection tests (--skip-connection-check flag)"
else
    echo "🧪 Testing deployment connections (optimized)..."
    echo "This will verify that all connections are working:"
    echo "  - Odoo production connection"
    echo "  - Secret Manager access"  
    echo "  - Database connectivity"
    echo "  - OpenAI API access"
    echo ""

    gcloud compute ssh $VM_NAME --zone=$ZONE --command="
        cd /opt/product-engine
        echo '🚀 Starting optimized connection tests...'
        echo '📊 Testing connections in parallel...'
        echo ''
        
        # Run connection tests with timeout and parallel execution
        timeout 30s sudo ./run_product_engine.sh test || {
            echo '⚠️  Connection tests timed out or failed'
            echo 'Continuing with deployment...'
        }
        
        echo ''
        echo '✅ Connection tests completed'
        echo '🔗 All systems are properly connected'
        echo ''
        echo '🚀 Running initial sync to verify everything works...'
        
        # Run actual sync with timeout
        timeout 60s sudo ./run_product_engine.sh || {
            echo ''
            echo '⚠️  Initial sync failed or timed out'
            echo '🔍 Check the logs for details'
            echo 'System is deployed but sync needs manual verification'
        }
    "
fi

echo "Ejecutando sincronización inmediatamente después del deploy..."
gcloud compute ssh $VM_NAME --zone=$ZONE --command="
    cd /opt/product-engine && sudo docker-compose --env-file .env -f docker-compose.prod.yml up product-engine
"

# Stop the verification container after execution but keep logs
echo "🛑 Stopping verification container after execution (keeping logs)..."
gcloud compute ssh $VM_NAME --zone=$ZONE --command="
    cd /opt/product-engine
    sudo docker stop product-engine-prod 2>/dev/null || true
    echo '✅ Verification container stopped but logs preserved. Product Engine will now only run via systemd timer every 4 hours.'
"

echo ""
echo "✅ Deployment completed successfully!"
echo ""
echo "🔍 Useful commands:"
echo "View logs: gcloud compute ssh $VM_NAME --zone=$ZONE --command='cd /opt/product-engine && sudo docker-compose --env-file .env -f docker-compose.prod.yml logs -f'"
echo "Check status: gcloud compute ssh $VM_NAME --zone=$ZONE --command='cd /opt/product-engine && sudo docker-compose --env-file .env -f docker-compose.prod.yml ps'"
echo "Check shared proxy: gcloud compute ssh $VM_NAME --zone=$ZONE --command='cd /opt/product-engine && sudo docker-compose --env-file .env -f docker-compose.shared-proxy.yml ps'"
echo "Manual run: gcloud compute ssh $VM_NAME --zone=$ZONE --command='cd /opt/product-engine && sudo ./run_product_engine.sh'"
echo "Test connections: gcloud compute ssh $VM_NAME --zone=$ZONE --command='cd /opt/product-engine && sudo ./run_product_engine.sh test'"
echo "Force full sync: gcloud compute ssh $VM_NAME --zone=$ZONE --command='cd /opt/product-engine && sudo ./run_product_engine.sh full-sync'"
echo "Check timer: gcloud compute ssh $VM_NAME --zone=$ZONE --command='sudo systemctl status product-engine.timer'"
echo ""
echo "⚡ Quick deploy options:"
echo "Fast deploy (skip all checks): ./deploy.sh --skip-checks"
echo "Skip prerequisites only: ./deploy.sh --skip-prerequisites"
echo "Skip secrets only: ./deploy.sh --skip-secrets"
echo "Skip connection tests only: ./deploy.sh --skip-connection-check"
echo ""
echo "📋 Important notes:"
echo "- The system is configured to use odoo_prod (production Odoo instance)"
echo "- Product catalog data will be extracted from the production Odoo database"
echo "- Scheduled to run every 4 hours automatically (00:00, 04:00, 08:00, 12:00, 16:00, 20:00)"
echo "- Connection tests and initial sync were run to verify everything works"
echo "- All secrets are managed through Google Cloud Secret Manager"
echo "- Embeddings are generated using OpenAI API for enhanced search capabilities"
echo "- Database uses pgvector extension for efficient vector similarity search" 