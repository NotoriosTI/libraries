#!/bin/bash

# Script de configuración para Prompt Assistant
echo "🚀 Configurando Prompt Assistant..."

# Verificar si Poetry está instalado
if ! command -v poetry &> /dev/null; then
    echo "📦 Instalando Poetry..."
    curl -sSL https://install.python-poetry.org | python3 -
    echo "✅ Poetry instalado"
else
    echo "✅ Poetry ya está instalado"
fi

# Instalar dependencias
echo "📚 Instalando dependencias..."
poetry install

# Crear archivo .env si no existe
if [ ! -f .env ]; then
    echo "🔧 Creando archivo .env..."
    cat > .env << EOF
# Google Gemini API Key
# Obtén tu API key en: https://makersuite.google.com/app/apikey
GOOGLE_API_KEY=your_google_api_key_here

# Configuración opcional del modelo
# MODEL_NAME=gemini-2.0-flash-exp
# TEMPERATURE=0.7
EOF
    echo "⚠️  IMPORTANTE: Edita el archivo .env y agrega tu GOOGLE_API_KEY"
else
    echo "✅ Archivo .env ya existe"
fi

# Ejecutar pruebas
echo "🧪 Ejecutando pruebas..."
poetry run pytest

echo "🎉 Configuración completada!"
echo ""
echo "Para usar el proyecto:"
echo "1. Edita .env y agrega tu GOOGLE_API_KEY"
echo "2. Ejecuta: poetry run prompt-assistant"
echo "3. O activa el entorno: poetry shell" 