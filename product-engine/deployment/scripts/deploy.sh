#!/bin/bash

# deployment/scripts/deploy.sh
# Deployment Script for Product Engine

set -e  # Exit on any error

# Configuration
PROJECT_ID="notorios"  # Hardcoded project ID
REGION=${1:-"us-central1"}
ZONE=${2:-"us-central1-c"}
VM_NAME="langgraph"
IMAGE_NAME="gcr.io/$PROJECT_ID/product-engine"
VERSION=${3:-$(date +%Y%m%d-%H%M%S)}
INSTANCE_NAME="app"  # Replace with actual Cloud SQL instance name

echo "🚀 Deploying Product Engine"
echo "Project: $PROJECT_ID"
echo "VM: $VM_NAME"
echo "Region: $REGION"
echo "Zone: $ZONE"
echo "Image: $IMAGE_NAME:$VERSION"
echo "Cloud SQL Instance: $INSTANCE_NAME"

# Function to check prerequisites
check_prerequisites() {
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
    echo "🔐 Setting up VM environment..."
    
    # Create directory structure on VM and setup Docker permissions
    gcloud compute ssh $VM_NAME --zone=$ZONE --command="
        # Create product-engine directory
        sudo mkdir -p /opt/product-engine
        sudo chown \$(whoami):\$(whoami) /opt/product-engine
        
        # Add current user to docker group if not already
        if ! groups \$(whoami) | grep -q docker; then
            echo 'Adding user to docker group...'
            sudo usermod -aG docker \$(whoami)
            echo 'User added to docker group. Note: Changes take effect on next login.'
        else
            echo 'User already in docker group.'
        fi
        
        echo 'VM environment setup completed.'
    "
}

# Function to verify required secrets exist
verify_secrets() {
    echo "🔐 Verifying required secrets in Secret Manager..."
    
    REQUIRED_SECRETS=(
        "ODOO_PROD_URL" "ODOO_PROD_DB" "ODOO_PROD_USERNAME" "ODOO_PROD_PASSWORD"
        "DB_HOST" "DB_PORT" "DB_NAME" "DB_USER" "DB_PASSWORD"
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
docker build --platform linux/amd64 -f deployment/Dockerfile -t $IMAGE_NAME:$VERSION -t $IMAGE_NAME:latest .

echo "📤 Pushing to Container Registry..."
# Configure Docker to use gcloud as credential helper
gcloud auth configure-docker --quiet

docker push $IMAGE_NAME:$VERSION
docker push $IMAGE_NAME:latest

# Setup VM environment
setup_vm_environment

# Deploy to VM
echo "🚚 Deploying to VM..."

# Copy deployment files
gcloud compute scp deployment/docker-compose.prod.yml $VM_NAME:/opt/product-engine/ --zone=$ZONE

# SSH into VM and deploy
gcloud compute ssh $VM_NAME --zone=$ZONE --command="
    cd /opt/product-engine
    
    # Configure Docker to use gcloud credentials on VM
    echo '🔐 Configuring Docker authentication for GCR...'
    gcloud auth configure-docker gcr.io --quiet
    
    # Also authenticate sudo docker
    sudo gcloud auth configure-docker gcr.io --quiet
    
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
    
    # Stop existing containers gracefully
    sudo docker-compose -f docker-compose.prod.yml down --timeout 30 || true
    
    # Remove any orphaned containers
    sudo docker system prune -f
    
    # Start services with environment file
    sudo docker-compose --env-file .env -f docker-compose.prod.yml up -d
    
    # Wait for services to be ready
    echo '⏳ Waiting for services to start...'
    sleep 15
    
    # Check if services are running
    if sudo docker-compose --env-file .env -f docker-compose.prod.yml ps | grep -q 'Up'; then
        echo '✅ Services are running'
        sudo docker-compose --env-file .env -f docker-compose.prod.yml ps
    else
        echo '❌ Services failed to start'
        sudo docker-compose --env-file .env -f docker-compose.prod.yml logs
        exit 1
    fi
"

# Set up systemd service and timer for scheduled execution
echo "⏰ Setting up scheduled execution..."
gcloud compute ssh $VM_NAME --zone=$ZONE --command="
    # Create systemd service for product sync
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
ExecStart=/usr/bin/sudo /usr/local/bin/docker-compose --env-file .env -f docker-compose.prod.yml run --rm product-engine

[Install]
WantedBy=multi-user.target
EOF

    # Create systemd timer (every 4 hours)
    sudo tee /etc/systemd/system/product-engine.timer > /dev/null << 'EOF'
[Unit]
Description=Run Product Engine every 4 hours
Requires=product-engine.service

[Timer]
OnCalendar=*-*-* 00,04,08,12,16,20:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

    # Enable and start timer
    sudo systemctl daemon-reload
    sudo systemctl enable product-engine.timer
    sudo systemctl start product-engine.timer
    
    echo '⏰ Scheduled execution configured (every 4 hours)'
    sudo systemctl list-timers product-engine.timer
"

# Test the deployment with connection test
echo "🧪 Testing deployment connections..."
echo "This will verify that all connections are working:"
echo "  - Odoo production connection"
echo "  - Secret Manager access"  
echo "  - Database connectivity"
echo "  - OpenAI API access"
echo ""

gcloud compute ssh $VM_NAME --zone=$ZONE --command="
    cd /opt/product-engine
    echo '🚀 Starting connection tests...'
    echo '📊 This will test all system connections:'
    echo ''
    
    # Run connection tests
    if sudo docker-compose --env-file .env -f docker-compose.prod.yml run --rm -e TEST_CONNECTIONS_ONLY=true product-engine; then
        echo ''
        echo '✅ Connection tests passed!'
        echo '🔗 All systems are properly connected'
        echo ''
        echo '🚀 Running initial sync to verify everything works...'
        
        # Run actual sync
        if sudo docker-compose --env-file .env -f docker-compose.prod.yml run --rm product-engine; then
            echo ''
            echo '✅ Initial sync completed successfully!'
            echo '📊 Product catalog synchronization is working correctly'
        else
            echo ''
            echo '❌ Initial sync failed!'
            echo '🔍 Check the logs above for details'
            exit 1
        fi
    else
        echo ''
        echo '❌ Connection tests failed!'
        echo '🔍 Check the logs above for details'
        echo ''
        echo 'Common issues to check:'
        echo '  - Odoo production credentials in Secret Manager'
        echo '  - Database connection and pgvector extension'
        echo '  - OpenAI API key and quota'
        echo '  - Network connectivity'
        exit 1
    fi
"

echo ""
echo "✅ Deployment completed successfully!"
echo ""
echo "🔍 Useful commands:"
echo "View logs: gcloud compute ssh $VM_NAME --zone=$ZONE --command='cd /opt/product-engine && sudo docker-compose --env-file .env -f docker-compose.prod.yml logs -f'"
echo "Check status: gcloud compute ssh $VM_NAME --zone=$ZONE --command='cd /opt/product-engine && sudo docker-compose --env-file .env -f docker-compose.prod.yml ps'"
echo "Manual run: gcloud compute ssh $VM_NAME --zone=$ZONE --command='cd /opt/product-engine && sudo docker-compose --env-file .env -f docker-compose.prod.yml run --rm product-engine'"
echo "Test connections: gcloud compute ssh $VM_NAME --zone=$ZONE --command='cd /opt/product-engine && sudo docker-compose --env-file .env -f docker-compose.prod.yml run --rm -e TEST_CONNECTIONS_ONLY=true product-engine'"
echo "Force full sync: gcloud compute ssh $VM_NAME --zone=$ZONE --command='cd /opt/product-engine && sudo docker-compose --env-file .env -f docker-compose.prod.yml run --rm -e FORCE_FULL_SYNC=true product-engine'"
echo "Check timer: gcloud compute ssh $VM_NAME --zone=$ZONE --command='sudo systemctl status product-engine.timer'"
echo ""
echo "📋 Important notes:"
echo "- The system is configured to use odoo_prod (production Odoo instance)"
echo "- Product catalog data will be extracted from the production Odoo database"
echo "- Scheduled to run every 4 hours automatically (00:00, 04:00, 08:00, 12:00, 16:00, 20:00)"
echo "- Connection tests and initial sync were run to verify everything works"
echo "- All secrets are managed through Google Cloud Secret Manager"
echo "- Embeddings are generated using OpenAI API for enhanced search capabilities"
echo "- Database uses pgvector extension for efficient vector similarity search" 