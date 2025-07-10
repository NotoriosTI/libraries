#!/bin/bash

# Script para ejecutar la sincronización de productos localmente
# Simula el entorno productivo pero sin contenedor Docker

set -e

# Parsear argumentos
FORCE_FULL_SYNC=false
TEST_CONNECTIONS_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --full-sync)
            FORCE_FULL_SYNC=true
            shift
            ;;
        --test-connections)
            TEST_CONNECTIONS_ONLY=true
            shift
            ;;
        *)
            echo "Argumento desconocido: $1"
            shift
            ;;
    esac
done

# Cargar variables de entorno desde .env si existe
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
  echo "✅ Variables de entorno cargadas desde .env"
else
  echo "⚠️  No se encontró archivo .env, se usarán variables del entorno actual"
fi

# Exportar flags según argumentos
export FORCE_FULL_SYNC
export TEST_CONNECTIONS_ONLY

echo "FORCE_FULL_SYNC=$FORCE_FULL_SYNC"
echo "TEST_CONNECTIONS_ONLY=$TEST_CONNECTIONS_ONLY"

# Ejecutar el sync agregando src/ al PYTHONPATH solo para este proceso
if command -v poetry &> /dev/null; then
  echo "🚀 Ejecutando sync con Poetry..."
  poetry run env PYTHONPATH=src python -m db_manager.sync_manager
else
  echo "🚀 Ejecutando sync con Python (sin Poetry)..."
  PYTHONPATH=src python -m db_manager.sync_manager
fi 