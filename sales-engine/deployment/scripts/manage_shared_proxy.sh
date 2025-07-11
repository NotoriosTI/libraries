#!/bin/bash

# deployment/scripts/manage_shared_proxy.sh
# Script para manejar el proxy compartido de Cloud SQL desde Sales Engine

set -e  # Exit on any error

# Configuration
PROJECT_ID="notorios"
REGION=${1:-"us-central1"}
INSTANCE_NAME="app-temp"

# Function to show usage
show_usage() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  start     Start the shared Cloud SQL proxy"
    echo "  stop      Stop the shared Cloud SQL proxy"
    echo "  restart   Restart the shared Cloud SQL proxy"
    echo "  status    Show status of the shared proxy"
    echo "  logs      Show logs of the shared proxy"
    echo "  help      Show this help message"
    echo ""
    echo "Options:"
    echo "  --region REGION     Specify region (default: us-central1)"
    echo ""
    echo "Examples:"
    echo "  $0 start                    # Start shared proxy"
    echo "  $0 status                   # Check proxy status"
    echo "  $0 stop                     # Stop shared proxy"
    echo "  $0 --region us-east1 start # Start with different region"
}

# Parse command line arguments
COMMAND=""
while [[ $# -gt 0 ]]; do
    case $1 in
        start|stop|restart|status|logs|help)
            COMMAND="$1"
            shift
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

if [ -z "$COMMAND" ]; then
    show_usage
    exit 1
fi

if [ "$COMMAND" = "help" ]; then
    show_usage
    exit 0
fi

echo "🔗 Managing shared Cloud SQL proxy (from Sales Engine)"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Instance: $INSTANCE_NAME"
echo "Command: $COMMAND"
echo ""

# Check if we're running on the VM or locally
if [ -f "/opt/sales-engine/.env" ]; then
    echo "📍 Running on VM..."
    cd /opt/sales-engine
    
    case $COMMAND in
        start)
            echo "🚀 Starting shared Cloud SQL proxy..."
            # Try to start from product-engine first, fallback to direct command
            if [ -f "/opt/product-engine/docker-compose.shared-proxy.yml" ]; then
                cd /opt/product-engine
                sudo docker-compose --env-file .env -f docker-compose.shared-proxy.yml up -d
                echo "✅ Shared proxy started via product-engine"
            else
                # Direct docker command as fallback
                sudo docker run -d --name shared-cloud-sql-proxy --network host --restart unless-stopped gcr.io/cloudsql-docker/gce-proxy:1.33.2 /cloud_sql_proxy -instances=$PROJECT_ID:$REGION:$INSTANCE_NAME=tcp:0.0.0.0:5432
                echo "✅ Shared proxy started directly"
            fi
            ;;
        stop)
            echo "🛑 Stopping shared Cloud SQL proxy..."
            sudo docker stop shared-cloud-sql-proxy || true
            sudo docker rm shared-cloud-sql-proxy || true
            echo "✅ Shared proxy stopped"
            ;;
        restart)
            echo "🔄 Restarting shared Cloud SQL proxy..."
            $0 stop
            sleep 2
            $0 start
            ;;
        status)
            echo "📊 Shared proxy status:"
            sudo docker ps --filter name=shared-cloud-sql-proxy --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
            ;;
        logs)
            echo "📋 Shared proxy logs:"
            sudo docker logs -f shared-cloud-sql-proxy
            ;;
    esac
else
    echo "📍 Running locally, connecting to VM..."
    
    case $COMMAND in
        start)
            echo "🚀 Starting shared Cloud SQL proxy on VM..."
            gcloud compute ssh langgraph --zone=us-central1-c --command="
                cd /opt/sales-engine
                if [ -f '/opt/product-engine/docker-compose.shared-proxy.yml' ]; then
                    cd /opt/product-engine
                    sudo docker-compose --env-file .env -f docker-compose.shared-proxy.yml up -d
                    echo '✅ Shared proxy started via product-engine'
                else
                    sudo docker run -d --name shared-cloud-sql-proxy --network host --restart unless-stopped gcr.io/cloudsql-docker/gce-proxy:1.33.2 /cloud_sql_proxy -instances=$PROJECT_ID:$REGION:$INSTANCE_NAME=tcp:0.0.0.0:5432
                    echo '✅ Shared proxy started directly'
                fi
            "
            ;;
        stop)
            echo "🛑 Stopping shared Cloud SQL proxy on VM..."
            gcloud compute ssh langgraph --zone=us-central1-c --command="
                sudo docker stop shared-cloud-sql-proxy || true
                sudo docker rm shared-cloud-sql-proxy || true
                echo '✅ Shared proxy stopped'
            "
            ;;
        restart)
            echo "🔄 Restarting shared Cloud SQL proxy on VM..."
            gcloud compute ssh langgraph --zone=us-central1-c --command="
                cd /opt/sales-engine
                sudo docker stop shared-cloud-sql-proxy || true
                sudo docker rm shared-cloud-sql-proxy || true
                sleep 2
                if [ -f '/opt/product-engine/docker-compose.shared-proxy.yml' ]; then
                    cd /opt/product-engine
                    sudo docker-compose --env-file .env -f docker-compose.shared-proxy.yml up -d
                    echo '✅ Shared proxy restarted via product-engine'
                else
                    sudo docker run -d --name shared-cloud-sql-proxy --network host --restart unless-stopped gcr.io/cloudsql-docker/gce-proxy:1.33.2 /cloud_sql_proxy -instances=$PROJECT_ID:$REGION:$INSTANCE_NAME=tcp:0.0.0.0:5432
                    echo '✅ Shared proxy restarted directly'
                fi
            "
            ;;
        status)
            echo "📊 Shared proxy status on VM:"
            gcloud compute ssh langgraph --zone=us-central1-c --command="
                sudo docker ps --filter name=shared-cloud-sql-proxy --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
            "
            ;;
        logs)
            echo "📋 Shared proxy logs from VM:"
            gcloud compute ssh langgraph --zone=us-central1-c --command="
                sudo docker logs -f shared-cloud-sql-proxy
            "
            ;;
    esac
fi

echo ""
echo "✅ Shared proxy management completed!" 