#!/bin/bash

# deployment/scripts/test_deploy.sh  
# Test Deployment Script for Product Engine

set -e  # Exit on any error

echo "🧪 PRODUCT ENGINE - TEST DEPLOYMENT"
echo "===================================="

# Configuration
PROJECT_ID="notorios"
REGION=${1:-"us-central1"}
INSTANCE_NAME="app"
TEST_TYPE=${2:-"all"}  # setup, complete, integration, search, pytest, all

# Check if we're in the correct directory
if [[ ! -f "tests/deployment/docker-compose.test.yml" ]]; then
    echo "❌ Error: Must be run from product-engine root directory"
    exit 1
fi

# Function to check prerequisites
check_prerequisites() {
    echo "🔍 Checking prerequisites..."
    
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
    
    # Check if .env file exists
    if [[ ! -f ".env" ]]; then
        echo "⚠️  Warning: .env file not found. Creating basic .env file..."
        cat > .env << EOF
# Test Environment Configuration
ENVIRONMENT=local_machine
GCP_PROJECT_ID=$PROJECT_ID
REGION=$REGION
INSTANCE_NAME=$INSTANCE_NAME
USE_TEST_ODOO=true
FORCE_FULL_SYNC=false
TEST_CONNECTIONS_ONLY=false
PYTEST_VERBOSITY=2
RUN_INTEGRATION_TESTS=false
EOF
        echo "✅ Created .env file with test configuration"
    fi
    
    echo "✅ Prerequisites check passed"
}

# Function to build test image
build_test_image() {
    echo "🐳 Building test Docker image..."
    
    # Build the test image
    docker-compose -f tests/deployment/docker-compose.test.yml build product-engine-test
    
    echo "✅ Test image built successfully"
}

# Function to start services
start_services() {
    echo "🚀 Starting test services..."
    
    # Export environment variables from test.env
    export $(cat tests/deployment/test.env | grep -v ^# | xargs)
    
    # Check if cloud-sql-proxy is running on host
    if ! nc -z 127.0.0.1 5432 2>/dev/null; then
        echo "❌ Error: Cloud SQL proxy is not running on host"
        echo "Please start the proxy first:"
        echo "  cd ../database_config && ./start_proxy.sh &"
        exit 1
    fi
    
    echo "✅ Cloud SQL proxy detected on host (127.0.0.1:5432)"
}

# Function to run tests
run_tests() {
    echo "🧪 Running tests: $TEST_TYPE"
    
    case "$TEST_TYPE" in
        "setup")
            echo "🔧 Running setup tests..."
            docker-compose -f tests/deployment/docker-compose.test.yml run --rm product-engine-test /app/run_tests.sh setup
            ;;
        "complete")
            echo "🧪 Running complete tests..."
            docker-compose -f tests/deployment/docker-compose.test.yml run --rm product-engine-test /app/run_tests.sh complete
            ;;
        "integration")
            echo "🔗 Running integration tests..."
            docker-compose -f tests/deployment/docker-compose.test.yml run --rm product-engine-test /app/run_tests.sh integration
            ;;
        "search")
            echo "🔍 Running search tests..."
            docker-compose -f tests/deployment/docker-compose.test.yml run --rm product-engine-test /app/run_tests.sh search
            ;;
        "pytest")
            echo "🧪 Running pytest suite..."
            docker-compose -f tests/deployment/docker-compose.test.yml run --rm product-engine-test /app/run_tests.sh pytest
            ;;
        "all")
            echo "🚀 Running all tests..."
            docker-compose -f tests/deployment/docker-compose.test.yml run --rm product-engine-test /app/run_tests.sh all
            ;;
        *)
            echo "❌ Unknown test type: $TEST_TYPE"
            echo "Available types: setup, complete, integration, search, pytest, all"
            exit 1
            ;;
    esac
}

# Function to cleanup
cleanup() {
    echo "🧹 Cleaning up test environment..."
    
    # Stop and remove containers
    docker-compose -f tests/deployment/docker-compose.test.yml down
    
    # Remove test volumes (optional)
    if [[ "${CLEAN_VOLUMES:-false}" == "true" ]]; then
        docker-compose -f tests/deployment/docker-compose.test.yml down -v
        echo "✅ Volumes cleaned"
    fi
    
    echo "✅ Cleanup completed"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [REGION] [TEST_TYPE]"
    echo ""
    echo "Arguments:"
    echo "  REGION     GCP region (default: us-central1)"
    echo "  TEST_TYPE  Type of test to run (default: all)"
    echo ""
    echo "Test types:"
    echo "  setup      - Run setup and configuration tests"
    echo "  complete   - Run complete db manager tests"
    echo "  integration- Run integration tests with Odoo"
    echo "  search     - Run search functionality tests"
    echo "  pytest     - Run pytest test suite"
    echo "  all        - Run all tests in sequence"
    echo ""
    echo "Examples:"
    echo "  $0                           # Run all tests"
    echo "  $0 us-central1 setup         # Run setup tests"
    echo "  $0 us-west1 complete         # Run complete tests in us-west1"
    echo ""
    echo "Environment variables:"
    echo "  CLEAN_VOLUMES=true           # Clean volumes after tests"
    echo "  USE_TEST_ODOO=false          # Use production Odoo (careful!)"
}

# Main execution
main() {
    # Show usage if help requested
    if [[ "$1" == "-h" || "$1" == "--help" ]]; then
        show_usage
        exit 0
    fi
    
    echo "Configuration:"
    echo "  Project ID: $PROJECT_ID"
    echo "  Region: $REGION"
    echo "  Test Type: $TEST_TYPE"
    echo ""
    
    # Run the deployment steps
    check_prerequisites
    build_test_image
    start_services
    
    # Set trap to cleanup on exit
    trap cleanup EXIT
    
    # Run the tests
    run_tests
    
    echo ""
    echo "✅ Test deployment completed successfully!"
    echo ""
    echo "🔍 Useful commands:"
    echo "  View logs: docker-compose -f tests/deployment/docker-compose.test.yml logs"
    echo "  Run specific test: docker-compose -f tests/deployment/docker-compose.test.yml run --rm product-engine-test /app/run_tests.sh [TEST_TYPE]"
    echo "  Interactive shell: docker-compose -f tests/deployment/docker-compose.test.yml run --rm product-engine-test bash"
    echo "  Manual cleanup: docker-compose -f tests/deployment/docker-compose.test.yml down"
}

# Run main function
main "$@" 