#!/bin/bash

# deployment/scripts/deploy.sh
# Deployment Script for Sales Engine

set -e  # Exit on any error

# Configuration
PROJECT_ID="notorios"  # Hardcoded project ID
REGION=${1:-"us-central1"}
ZONE=${2:-"us-central1-c"}
VM_NAME="langgraph"
IMAGE_NAME="gcr.io/$PROJECT_ID/sales-engine"
VERSION=${3:-$(date +%Y%m%d-%H%M%S)}
INSTANCE_NAME="app"  # TODO: Replace with actual instance name

echo "🚀 Deploying Sales Engine"
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

# Function to setup credentials on VM if needed
setup_vm_credentials() {
    echo "🔐 Setting up credentials on VM..."
    
    # Check if credentials file exists on VM
    if ! gcloud compute ssh $VM_NAME --zone=$ZONE --command="test -f /opt/sales-engine/credentials.json" 2>/dev/null; then
        echo "⚠️  Credentials file not found on VM. Setting up service account..."
        
        # Create service account key (in production, this should be done separately)
        SERVICE_ACCOUNT="sales-engine@$PROJECT_ID.iam.gserviceaccount.com"
        
        echo "Note: In production, credentials should be managed through VM service accounts"
        echo "For now, ensure the VM has the necessary service account attached"
        
        # Create directory structure on VM and setup Docker permissions
        gcloud compute ssh $VM_NAME --zone=$ZONE --command="
            sudo mkdir -p /opt/sales-engine
            sudo chown \$(whoami):\$(whoami) /opt/sales-engine
            
            # Add current user to docker group if not already
            if ! groups \$(whoami) | grep -q docker; then
                echo 'Adding user to docker group...'
                sudo usermod -aG docker \$(whoami)
                echo 'User added to docker group. Note: Changes take effect on next login.'
            else
                echo 'User already in docker group.'
            fi
        "
    fi
}

# Run prerequisites check
check_prerequisites

# Build and push Docker image
echo "🐳 Building Docker image for linux/amd64..."
docker build --platform linux/amd64 -f deployment/Dockerfile -t $IMAGE_NAME:$VERSION -t $IMAGE_NAME:latest .

echo "📤 Pushing to Container Registry..."
# Configure Docker to use gcloud as credential helper
gcloud auth configure-docker --quiet

docker push $IMAGE_NAME:$VERSION
docker push $IMAGE_NAME:latest

# Setup VM if needed
setup_vm_credentials

# Deploy to VM
echo "🚚 Deploying to VM..."
gcloud compute scp deployment/docker-compose.prod.yml $VM_NAME:/opt/sales-engine/ --zone=$ZONE

# SSH into VM and deploy  
gcloud compute ssh $VM_NAME --zone=$ZONE --command="
    cd /opt/sales-engine
    
    # Configure Docker to use gcloud credentials on VM
    echo '🔐 Configuring Docker authentication for GCR...'
    gcloud auth configure-docker gcr.io --quiet
    
    # Also authenticate sudo docker
    sudo gcloud auth configure-docker gcr.io --quiet
    
    # Check if shared proxy is running
    echo '🔍 Checking if shared Cloud SQL proxy is running...'
    if ! sudo docker ps --format 'table {{.Names}}' | grep -q 'shared-cloud-sql-proxy'; then
        echo '⚠️  Shared proxy not found. Starting it from product-engine...'
        if [ -f '/opt/product-engine/docker-compose.shared-proxy.yml' ]; then
            cd /opt/product-engine
            sudo docker-compose --env-file .env -f docker-compose.shared-proxy.yml up -d
            echo '✅ Shared proxy started successfully'
            cd /opt/sales-engine
        else
            echo '❌ Error: Shared proxy configuration not found in /opt/product-engine/'
            echo 'Please ensure product-engine is deployed first or start the shared proxy manually:'
            echo 'sudo docker run -d --name shared-cloud-sql-proxy --network host --restart unless-stopped gcr.io/cloudsql-docker/gce-proxy:1.33.2 /cloud_sql_proxy -instances=notorios:us-central1:app-temp=tcp:0.0.0.0:5432'
            exit 1
        fi
    else
        echo '✅ Shared proxy is already running'
    fi
    
    # Create environment file for docker-compose
    cat > .env << EOF
PROJECT_ID=$PROJECT_ID
REGION=$REGION
INSTANCE=$INSTANCE_NAME
USE_TEST_ODOO=false
EOF
    
    # Verify deployment environment
    echo '🔍 Deployment environment:'
    echo \"PROJECT_ID: $PROJECT_ID\"
    echo \"REGION: $REGION\"
    echo \"INSTANCE: $INSTANCE_NAME\"
    echo 'USE_TEST_ODOO: false (uses odoo_prod)'
    echo 'DB_HOST: 127.0.0.1 (using shared proxy)'
    
    # Pull latest image (use sudo in case user group changes haven't taken effect)
    echo \"🐳 Pulling image: $PROJECT_ID/sales-engine:latest\"
    sudo docker pull gcr.io/$PROJECT_ID/sales-engine:latest
    
    # Stop existing containers gracefully
    sudo docker-compose -f docker-compose.prod.yml down --timeout 30 || true
    
    # Remove any orphaned containers
    sudo docker system prune -f
    
    # Start services for verification (will stop after execution)
    sudo docker-compose --env-file .env -f docker-compose.prod.yml up -d
    
    # Wait for services to be ready
    echo '⏳ Waiting for services to start...'
    sleep 10
    
    # Check if container was created and started successfully
    if sudo docker ps -a --format 'table {{.Names}}\t{{.Status}}' | grep -q 'sales-engine-prod'; then
        echo '✅ Sales Engine container started successfully'
        echo '📋 Container will run once and stop (no continuous restart)'
        
        # Wait a bit more for the container to complete its execution
        echo '⏳ Waiting for container to complete execution...'
        sleep 15
        
        # Check final status
        CONTAINER_STATUS=$(sudo docker ps -a --format 'table {{.Names}}\t{{.Status}}' | grep 'sales-engine-prod' | awk '{print $2}')
        if [[ "$CONTAINER_STATUS" == *"Exited (0)"* ]]; then
            echo '✅ Sales Engine executed successfully and stopped'
        elif [[ "$CONTAINER_STATUS" == *"Up"* ]]; then
            echo '✅ Sales Engine is running'
        else
            echo '❌ Sales Engine failed to execute properly'
            echo '🔍 Container status:'
            sudo docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}' | grep 'sales-engine-prod'
            echo '📋 Container logs:'
            sudo docker logs sales-engine-prod --tail 20
            exit 1
        fi
    else
        echo '❌ Sales Engine container failed to start'
        sudo docker-compose --env-file .env -f docker-compose.prod.yml logs
        exit 1
    fi
"

# Set up cron job for scheduled execution
echo "⏰ Setting up scheduled execution..."
gcloud compute ssh $VM_NAME --zone=$ZONE --command="
    # Create systemd service
    sudo tee /etc/systemd/system/sales-engine.service > /dev/null << 'EOF'
[Unit]
Description=Sales Engine Database Updater
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
WorkingDirectory=/opt/sales-engine
Environment=PROJECT_ID=$PROJECT_ID
Environment=REGION=$REGION
Environment=INSTANCE=$INSTANCE_NAME
ExecStart=/usr/bin/sudo /usr/local/bin/docker-compose --env-file .env -f docker-compose.prod.yml run --rm sales-engine

[Install]
WantedBy=multi-user.target
EOF

    # Create systemd timer (every 4 hours)
    sudo tee /etc/systemd/system/sales-engine.timer > /dev/null << 'EOF'
[Unit]
Description=Run Sales Engine every 4 hours
Requires=sales-engine.service

[Timer]
OnCalendar=*-*-* 00,04,08,12,16,20:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

    # Enable and start timer
    sudo systemctl daemon-reload
    sudo systemctl enable sales-engine.timer
    sudo systemctl start sales-engine.timer
    
    echo '⏰ Scheduled execution configured (every 4 hours)'
    sudo systemctl list-timers sales-engine.timer
"

# Test the deployment with an immediate run
echo "🧪 Testing deployment with immediate execution..."
echo "This will verify that everything is working correctly:"
echo "  - Odoo production connection"
echo "  - Secret Manager access"
echo "  - Database synchronization"
echo ""

gcloud compute ssh $VM_NAME --zone=$ZONE --command="
    cd /opt/sales-engine
    echo '🚀 Starting test execution...'
    echo '📊 This will show real-time logs from the sales engine:'
    echo ''
    
    # Run the sales engine and capture the output
    if sudo docker-compose --env-file .env -f docker-compose.prod.yml run --rm sales-engine; then
        echo ''
        echo '✅ Test execution completed successfully!'
        echo '📈 Sales data synchronization is working correctly'
    else
        echo ''
        echo '❌ Test execution failed!'
        echo '🔍 Check the logs above for details'
        echo ''
        echo 'Common issues to check:'
        echo '  - Odoo production credentials'
        echo '  - Database connection'
        echo '  - Network connectivity'
        exit 1
    fi
"

# Stop the verification container after execution
echo "🛑 Stopping verification container after execution..."
gcloud compute ssh $VM_NAME --zone=$ZONE --command="
    cd /opt/sales-engine
    sudo docker stop sales-engine-prod 2>/dev/null || true
    sudo docker rm sales-engine-prod 2>/dev/null || true
    echo '✅ Verification container stopped. Sales Engine will now only run via systemd timer every 6 hours.'
"

echo ""
echo "✅ Deployment completed successfully!"
echo ""
echo "🔍 Useful commands:"
echo "View logs: gcloud compute ssh $VM_NAME --zone=$ZONE --command='cd /opt/sales-engine && sudo docker-compose --env-file .env -f docker-compose.prod.yml logs -f'"
echo "Check status: gcloud compute ssh $VM_NAME --zone=$ZONE --command='cd /opt/sales-engine && sudo docker-compose --env-file .env -f docker-compose.prod.yml ps'"
echo "Manual run: gcloud compute ssh $VM_NAME --zone=$ZONE --command='cd /opt/sales-engine && sudo docker-compose --env-file .env -f docker-compose.prod.yml run --rm sales-engine'"
echo "Check timer: gcloud compute ssh $VM_NAME --zone=$ZONE --command='sudo systemctl status sales-engine.timer'"
echo ""
echo "📋 Important notes:"
echo "- The system is configured to use odoo_prod (production Odoo instance)"
echo "- Data extraction will come from the production Odoo database"
echo "- Scheduled to run every 4 hours automatically (00:00, 04:00, 08:00, 12:00, 16:00, 20:00)"
echo "- A test execution was run immediately to verify everything works"
echo "- All secrets are managed through Google Cloud Secret Manager"
