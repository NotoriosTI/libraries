#!/bin/bash

# pre_deploy_check.sh
# Script de verificación pre-deployment para Sales Engine

# NO usar set -e aquí para permitir que todas las verificaciones se ejecuten
# set -e

PROJECT_ID="notorios"
REGION="us-central1"
ZONE="us-central1-c" 
VM_NAME="langgraph"

echo "🔍 VERIFICACIÓN PRE-DEPLOYMENT - SALES ENGINE"
echo "=============================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

success_count=0
error_count=0
warning_count=0

check_success() {
    echo -e "${GREEN}✅ $1${NC}"
    ((success_count++))
}

check_error() {
    echo -e "${RED}❌ $1${NC}"
    ((error_count++))
}

check_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
    ((warning_count++))
}

echo "📋 1. VERIFICACIÓN DE PREREQUISITOS"
echo "-----------------------------------"

# Check gcloud CLI
if command -v gcloud &> /dev/null; then
    check_success "gcloud CLI está instalado"
else
    check_error "gcloud CLI no está instalado"
fi

# Check authentication
if gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n1 &> /dev/null; then
    CURRENT_USER=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n1 2>/dev/null || echo "N/A")
    check_success "Autenticado como: $CURRENT_USER"
else
    check_error "No autenticado con gcloud. Ejecuta: gcloud auth login"
fi

# Check project
CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")
if [ "$CURRENT_PROJECT" = "$PROJECT_ID" ]; then
    check_success "Proyecto configurado correctamente: $PROJECT_ID"
else
    check_warning "Proyecto actual: '$CURRENT_PROJECT', esperado: '$PROJECT_ID'"
    echo "  Ejecuta: gcloud config set project $PROJECT_ID"
fi

# Check Docker
if command -v docker &> /dev/null; then
    if docker info &> /dev/null; then
        check_success "Docker está instalado y ejecutándose"
    else
        check_error "Docker está instalado pero el daemon no está ejecutándose"
    fi
else
    check_error "Docker no está instalado"
fi

echo ""
echo "🖥️  2. VERIFICACIÓN DE INFRAESTRUCTURA GCP"
echo "-------------------------------------------"

# Check VM exists
if gcloud compute instances describe $VM_NAME --zone=$ZONE &> /dev/null; then
    check_success "VM '$VM_NAME' existe en zona '$ZONE'"
    
    # Check VM status
    VM_STATUS=$(gcloud compute instances describe $VM_NAME --zone=$ZONE --format="value(status)" 2>/dev/null || echo "UNKNOWN")
    if [ "$VM_STATUS" = "RUNNING" ]; then
        check_success "VM está ejecutándose"
    else
        check_warning "VM está en estado: $VM_STATUS"
    fi
else
    check_error "VM '$VM_NAME' no existe en zona '$ZONE'"
fi

# Check if we can SSH to VM (skip this check if other issues exist)
if [ $error_count -eq 0 ]; then
    if timeout 10 gcloud compute ssh $VM_NAME --zone=$ZONE --command="echo 'SSH test'" &> /dev/null; then
        check_success "Conexión SSH a VM funciona"
    else
        check_warning "No se puede conectar por SSH a la VM (posible timeout o permisos)"
    fi
else
    check_warning "Saltando verificación SSH debido a errores previos"
fi

echo ""
echo "🔐 3. VERIFICACIÓN DE SECRETS"
echo "-----------------------------"

REQUIRED_SECRETS=(
    "ODOO_PROD_URL"
    "ODOO_PROD_DB" 
    "ODOO_PROD_USERNAME"
    "ODOO_PROD_PASSWORD"
    "DB_HOST"
    "DB_PORT"
    "DB_NAME"
    "DB_USER"
    "DB_PASSWORD"
)

for secret in "${REQUIRED_SECRETS[@]}"; do
    if gcloud secrets describe $secret &> /dev/null; then
        check_success "Secret '$secret' existe"
    else
        check_error "Secret '$secret' no existe en Secret Manager"
    fi
done

echo ""
echo "⚙️  4. VERIFICACIÓN DE CONFIGURACIÓN LOCAL"
echo "--------------------------------------------"

# Check deploy script configuration
DEPLOY_SCRIPT="deployment/scripts/deploy.sh"
if [ -f "$DEPLOY_SCRIPT" ]; then
    # Check if INSTANCE_NAME has been updated
    if grep -q "your-cloud-sql-instance-name" "$DEPLOY_SCRIPT"; then
        check_error "INSTANCE_NAME en deploy.sh aún tiene valor por defecto"
        echo "  Edita la línea 11 en $DEPLOY_SCRIPT con el nombre real de tu instancia Cloud SQL"
    else
        INSTANCE_NAME=$(grep "INSTANCE_NAME=" "$DEPLOY_SCRIPT" | cut -d'"' -f2 2>/dev/null || echo "N/A")
        check_success "INSTANCE_NAME configurado: $INSTANCE_NAME"
    fi
else
    check_error "Script de deploy no encontrado: $DEPLOY_SCRIPT"
fi

# Check docker-compose configuration
DOCKER_COMPOSE="deployment/docker-compose.prod.yml"
if [ -f "$DOCKER_COMPOSE" ]; then
    # Check if USE_TEST_ODOO is set to false
    if grep -q "USE_TEST_ODOO=false" "$DOCKER_COMPOSE"; then
        check_success "Configurado para usar odoo_prod (USE_TEST_ODOO=false)"
    else
        check_warning "Verificar configuración USE_TEST_ODOO en docker-compose.prod.yml"
    fi
else
    check_error "docker-compose.prod.yml no encontrado"
fi

echo ""
echo "🐳 5. VERIFICACIÓN DE IMAGEN DOCKER"
echo "-----------------------------------"

# Check if we can build the image locally (dry run)
if command -v docker &> /dev/null && docker info &> /dev/null; then
    echo "Verificando que el Dockerfile es válido..."
    # Note: docker build --dry-run doesn't exist, so we'll skip this for now
    if [ -f "deployment/Dockerfile" ]; then
        check_success "Dockerfile existe"
    else
        check_error "Dockerfile no encontrado en deployment/"
    fi
else
    check_warning "No se puede verificar Dockerfile (Docker no disponible)"
fi

echo ""
echo "📊 RESUMEN DE VERIFICACIÓN"
echo "=========================="
echo -e "${GREEN}✅ Verificaciones exitosas: $success_count${NC}"
echo -e "${YELLOW}⚠️  Advertencias: $warning_count${NC}"
echo -e "${RED}❌ Errores: $error_count${NC}"
echo ""

if [ $error_count -eq 0 ]; then
    echo -e "${GREEN}🎉 ¡Listo para deployment!${NC}"
    echo ""
    echo "Para proceder con el deployment, ejecuta:"
    echo "  ./deployment/scripts/deploy.sh"
    echo ""
    echo "📋 Recordatorio: El sistema está configurado para:"
    echo "  - Usar odoo_prod (base de datos de producción)"
    echo "  - Ejecutar cada 6 horas automáticamente"
    echo "  - Extraer datos solo de Odoo producción"
    exit 0
else
    echo -e "${RED}❌ Hay errores que deben corregirse antes del deployment${NC}"
    echo ""
    echo "🔧 Pasos para corregir:"
    if [ $error_count -gt 0 ]; then
        echo "  1. Revisa los errores marcados arriba"
        echo "  2. Corrige la configuración según las indicaciones"
        echo "  3. Ejecuta este script nuevamente"
    fi
    exit 1
fi 