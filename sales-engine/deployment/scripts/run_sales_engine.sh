#!/bin/bash

# deployment/scripts/run_sales_engine.sh
# Script to run Sales Engine with unified forecast table structure

set -e  # Exit on any error

# Configuration
PROJECT_ID="notorios"
# Default region; can be overridden with --region flag
REGION="us-central1"
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
    echo "  --skip-forecast     Skip forecast pipeline execution"
    echo "  --help             Show this help message"
    echo ""
    echo "Commands:"
    echo "  sync               Run sales synchronization + forecast (default)"
    echo "  test               Test connections only"
    echo "  full-sync          Force full synchronization + forecast"
    echo "  forecast-only      Run only forecast pipeline (skip sales sync)"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Normal sync + forecast"
    echo "  $0 --test-connections                 # Test connections only"
    echo "  $0 --force-full-sync                 # Force full sync + forecast"
    echo "  $0 --skip-forecast                   # Sync without forecast"
    echo "  $0 forecast-only                     # Only forecast pipeline"
    echo "  $0 --region us-east1                 # Use different region"
}

# Parse command line arguments
FORCE_FULL_SYNC=false
TEST_CONNECTIONS_ONLY=false
SKIP_FORECAST=false
FORECAST_ONLY=false
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
        --skip-forecast)
            SKIP_FORECAST=true
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
        forecast-only)
            COMMAND="forecast-only"
            FORECAST_ONLY=true
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
    FORECAST_ONLY=false
    echo "🧪 Running connection tests only..."
elif [ "$COMMAND" = "full-sync" ] || [ "$FORCE_FULL_SYNC" = true ]; then
    TEST_CONNECTIONS_ONLY=false
    FORCE_FULL_SYNC=true
    FORECAST_ONLY=false
    echo "🔄 Running full synchronization + forecast..."
elif [ "$COMMAND" = "forecast-only" ] || [ "$FORECAST_ONLY" = true ]; then
    TEST_CONNECTIONS_ONLY=false
    FORCE_FULL_SYNC=false
    FORECAST_ONLY=true
    echo "🎯 Running forecast pipeline only..."
else
    TEST_CONNECTIONS_ONLY=false
    FORCE_FULL_SYNC=false
    FORECAST_ONLY=false
    if [ "$SKIP_FORECAST" = true ]; then
        echo "🔄 Running incremental synchronization (forecast skipped)..."
    else
        echo "🔄 Running incremental synchronization + forecast..."
    fi
fi

echo "🚀 Starting Sales Engine"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Instance: $INSTANCE_NAME"
echo "Image: $IMAGE_NAME"
echo "Test connections only: $TEST_CONNECTIONS_ONLY"
echo "Force full sync: $FORCE_FULL_SYNC"
echo "Skip forecast: $SKIP_FORECAST"
echo "Forecast only: $FORECAST_ONLY"
echo ""

# Ensure required env vars are exported for docker compose
export PROJECT_ID="$PROJECT_ID"
export REGION="$REGION"
export INSTANCE_NAME="$INSTANCE_NAME"
export USE_TEST_ODOO=${USE_TEST_ODOO:-false}

# Check if we're running on the VM or locally
if [ -d "/opt/sales-engine" ]; then
    echo "📍 Running on VM, using local environment..."
    cd /opt/sales-engine
    
    # Export environment variables for docker-compose (no file modification)
    export PROJECT_ID=$PROJECT_ID
    export REGION=$REGION
    export INSTANCE_NAME=$INSTANCE_NAME
    export FORCE_FULL_SYNC=$FORCE_FULL_SYNC
    export TEST_CONNECTIONS_ONLY=$TEST_CONNECTIONS_ONLY
    export SKIP_FORECAST=$SKIP_FORECAST
    export FORECAST_ONLY=$FORECAST_ONLY
    
    # Run on VM using docker compose v2 if available, fallback to v1
    if docker compose version >/dev/null 2>&1; then
        sudo -E docker compose -f docker-compose.prod.yml up sales-engine
    else
        sudo -E docker-compose -f docker-compose.prod.yml up sales-engine
    fi
else
    echo "📍 Running locally, connecting to VM..."
    
    # Run locally but connect to VM
    gcloud compute ssh langgraph --zone=us-central1-c --command="
        cd /opt/sales-engine
        
        # Export environment variables for docker-compose (no file modification)
        export PROJECT_ID=$PROJECT_ID
        export REGION=$REGION
        export INSTANCE_NAME=$INSTANCE_NAME
        export FORCE_FULL_SYNC=$FORCE_FULL_SYNC
        export TEST_CONNECTIONS_ONLY=$TEST_CONNECTIONS_ONLY
        export SKIP_FORECAST=$SKIP_FORECAST
        export FORECAST_ONLY=$FORECAST_ONLY
        
        echo '🚀 Starting Sales Engine on VM...'
        if docker compose version >/dev/null 2>&1; then
            sudo -E docker compose -f docker-compose.prod.yml up sales-engine
        else
            sudo -E docker-compose -f docker-compose.prod.yml up sales-engine
        fi
    "
fi

echo ""
echo "✅ Sales Engine execution completed!"