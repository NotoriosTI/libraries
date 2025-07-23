#!/bin/bash

# deployment/scripts/run_sales_engine.sh
# Script to run Sales Engine using docker run directly

set -e  # Exit on any error

# Configuration
PROJECT_ID="notorios"
REGION=${1:-"us-central1"}
INSTANCE_NAME="app-temp"
IMAGE_NAME="gcr.io/$PROJECT_ID/sales-engine:latest"

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS] [COMMAND]"
    echo ""
    echo "Options:"
    echo "  --region REGION     Specify region (default: us-central1)"
    echo "  --force-full-sync   Force full synchronization"
    echo "  --test-connections  Only test connections"
    echo "  --help             Show this help message"
    echo ""
    echo "Commands:"
    echo "  sync               Run sales synchronization (default)"
    echo "  test               Test connections only"
    echo "  full-sync          Force full synchronization"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Normal sync"
    echo "  $0 --test-connections                 # Test connections only"
    echo "  $0 --force-full-sync                 # Force full sync"
    echo "  $0 --region us-east1                 # Use different region"
}

# Parse command line arguments
FORCE_FULL_SYNC=false
TEST_CONNECTIONS_ONLY=false
COMMAND="sync"

while [[ $# -gt 0 ]]; do
    case $1 in
        --region)
            REGION="$2"
            shift 2
            ;;
        --force-full-sync)
            FORCE_FULL_SYNC=true
            shift
            ;;
        --test-connections)
            TEST_CONNECTIONS_ONLY=true
            shift
            ;;
        --help)
            show_usage
            exit 0
            ;;
        sync)
            COMMAND="sync"
            shift
            ;;
        test)
            COMMAND="test"
            TEST_CONNECTIONS_ONLY=true
            shift
            ;;
        full-sync)
            COMMAND="full-sync"
            FORCE_FULL_SYNC=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Set environment variables based on command
if [ "$COMMAND" = "test" ] || [ "$TEST_CONNECTIONS_ONLY" = true ]; then
    TEST_CONNECTIONS_ONLY=true
    FORCE_FULL_SYNC=false
    echo "🧪 Running connection tests only..."
elif [ "$COMMAND" = "full-sync" ] || [ "$FORCE_FULL_SYNC" = true ]; then
    TEST_CONNECTIONS_ONLY=false
    FORCE_FULL_SYNC=true
    echo "🔄 Running full synchronization..."
else
    TEST_CONNECTIONS_ONLY=false
    FORCE_FULL_SYNC=false
    echo "🔄 Running incremental synchronization..."
fi

echo "🚀 Starting Sales Engine"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Instance: $INSTANCE_NAME"
echo "Image: $IMAGE_NAME"
echo "Test connections only: $TEST_CONNECTIONS_ONLY"
echo "Force full sync: $FORCE_FULL_SYNC"
echo ""

# Check if we're running on the VM or locally
if [ -f "/opt/sales-engine/.env" ]; then
    echo "📍 Running on VM, using local environment..."
    cd /opt/sales-engine
    
    # Update environment variables in .env file
    sed -i "s/FORCE_FULL_SYNC=.*/FORCE_FULL_SYNC=$FORCE_FULL_SYNC/" .env
    sed -i "s/TEST_CONNECTIONS_ONLY=.*/TEST_CONNECTIONS_ONLY=$TEST_CONNECTIONS_ONLY/" .env
    
    # Run on VM using docker-compose (keeps logs)
    sudo docker-compose --env-file .env -f docker-compose.prod.yml up sales-engine
else
    echo "📍 Running locally, connecting to VM..."
    
    # Run locally but connect to VM
    gcloud compute ssh langgraph --zone=us-central1-c --command="
        cd /opt/sales-engine
        
        # Update environment variables in .env file
        sed -i \"s/FORCE_FULL_SYNC=.*/FORCE_FULL_SYNC=$FORCE_FULL_SYNC/\" .env
        sed -i \"s/TEST_CONNECTIONS_ONLY=.*/TEST_CONNECTIONS_ONLY=$TEST_CONNECTIONS_ONLY/\" .env
        
        echo '🚀 Starting Sales Engine on VM...'
        sudo docker-compose --env-file .env -f docker-compose.prod.yml up sales-engine
    "
fi

echo ""
echo "✅ Sales Engine execution completed!"