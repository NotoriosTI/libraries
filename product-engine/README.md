# Product Engine

Una librería robusta y automatizada para sincronizar el catálogo de productos desde Odoo a PostgreSQL con generación de embeddings vectoriales usando OpenAI.

## 🎯 Objetivo

Desarrollar una librería en Python que actúe como un motor de sincronización de datos entre un sistema ERP Odoo y una base de datos PostgreSQL alojada en Google Cloud SQL, enfocándose exclusivamente en el catálogo de productos y enriqueciendo cada producto con embeddings vectoriales para búsquedas avanzadas.

## ✨ Características Principales

- **Sincronización Incremental**: Solo sincroniza productos nuevos o modificados
- **Embeddings Vectoriales**: Genera automáticamente embeddings usando OpenAI API
- **Búsqueda Vectorial**: Soporte completo para pgvector en PostgreSQL
- **Configuración Multi-Entorno**: Desarrollo local y producción en Google Cloud
- **Manejo Robusto de Errores**: Logging estructurado y recuperación automática
- **Operaciones en Lote**: Optimizado para grandes volúmenes de datos
- **Containerización**: Docker y Docker Compose listos para producción

## 🏗️ Arquitectura

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│                 │    │                 │    │                 │
│  Odoo ERP       │───►│ Product Engine  │───►│ PostgreSQL      │
│  (Productos)    │    │                 │    │ (+ pgvector)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │                 │
                       │  OpenAI API     │
                       │  (Embeddings)   │
                       └─────────────────┘
```

## 🔧 Componentes

### Módulos Principales

1. **`config.py`** - Gestión de configuración usando config-manager compartido
2. **`odoo_api.py`** - Extracción de datos de Odoo con sincronización incremental
3. **`embedding_generator.py`** - Generación de embeddings usando OpenAI API
4. **`database_updater.py`** - Operaciones de base de datos con soporte pgvector
5. **`main.py`** - Orquestador principal del proceso de sincronización

### Flujo de Sincronización

1. **Configuración**: Carga credenciales desde .env (desarrollo) o Secret Manager (producción)
2. **Extracción**: Lee productos de Odoo con filtros incrementales
3. **Upsert**: Actualiza/inserta productos en PostgreSQL usando operaciones en lote
4. **Desactivación**: Marca productos inactivos que ya no existen en Odoo
5. **Embeddings**: Genera y almacena vectores usando OpenAI para productos nuevos/modificados
6. **Finalización**: Registra timestamp de sincronización exitosa

## 🚀 Instalación

### Requisitos Previos

- Python 3.13+
- PostgreSQL con extensión pgvector
- Acceso a Odoo (producción o test)
- API Key de OpenAI
- Google Cloud credentials (para producción)

### Instalación Local

```bash
# Clonar el repositorio
git clone https://github.com/NotoriosTI/libraries.git
cd libraries/product-engine

# Instalar con Poetry
poetry install

# O instalar directamente desde Git
pip install git+https://github.com/NotoriosTI/libraries.git#subdirectory=product-engine
```

## ⚙️ Configuración

### Desarrollo Local

Crear archivo `.env` en el directorio raíz:

```env
# Entorno
ENVIRONMENT=local_machine

# Odoo Producción
ODOO_PROD_URL=https://tu-odoo-domain.com
ODOO_PROD_DB=tu_base_datos_produccion
ODOO_PROD_USERNAME=tu_usuario_api
ODOO_PROD_PASSWORD=tu_password_api

# Odoo Test (opcional)
ODOO_TEST_URL=https://tu-odoo-domain.com
ODOO_TEST_DB=tu_base_datos_test
ODOO_TEST_USERNAME=tu_usuario_test
ODOO_TEST_PASSWORD=tu_password_test

# Base de Datos PostgreSQL
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=products_db
DB_USER=postgres
DB_PASSWORD=tu_password

# OpenAI
OPENAI_API_KEY=sk-tu-api-key-de-openai

# Google Cloud (opcional para local)
GCP_PROJECT_ID=tu-project-id
```

### Producción (Google Cloud)

En producción, las credenciales se gestionan a través de Google Cloud Secret Manager:

```bash
# Crear secrets requeridos
gcloud secrets create ODOO_PROD_URL --data-file=-
gcloud secrets create ODOO_PROD_DB --data-file=-
gcloud secrets create ODOO_PROD_USERNAME --data-file=-
gcloud secrets create ODOO_PROD_PASSWORD --data-file=-
gcloud secrets create DB_HOST --data-file=-
gcloud secrets create DB_PORT --data-file=-
gcloud secrets create DB_NAME --data-file=-
gcloud secrets create DB_USER --data-file=-
gcloud secrets create DB_PASSWORD --data-file=-
gcloud secrets create OPENAI_API_KEY --data-file=-
```

## 💾 Esquema de Base de Datos

La tabla `products` se crea automáticamente con este esquema:

```sql
CREATE TABLE products (
    sku VARCHAR(100) PRIMARY KEY,
    name VARCHAR(500) NOT NULL,
    description TEXT,
    category_id INTEGER,
    category_name VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    list_price NUMERIC(15, 2) DEFAULT 0,
    standard_price NUMERIC(15, 2) DEFAULT 0,
    product_type VARCHAR(50),
    barcode VARCHAR(100),
    weight NUMERIC(10, 3) DEFAULT 0,
    volume NUMERIC(10, 3) DEFAULT 0,
    sale_ok BOOLEAN DEFAULT TRUE,
    purchase_ok BOOLEAN DEFAULT TRUE,
    uom_id INTEGER,
    uom_name VARCHAR(100),
    company_id INTEGER,
    text_for_embedding TEXT,
    embedding VECTOR(1536),  -- pgvector para embeddings
    last_update TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

## 🔄 Uso

### Uso Básico

```python
from product_engine import ProductsSyncEngine

# Inicializar el motor de sincronización
engine = ProductsSyncEngine(use_test_odoo=False)

# Ejecutar sincronización
results = engine.run_sync()

# Verificar resultados
if results["success"]:
    print(f"✅ Sincronizados {results['products_processed']} productos")
    print(f"📊 Embeddings generados: {results['embeddings_generated']}")
else:
    print(f"❌ Error: {results['error']}")
```

### Línea de Comandos

```bash
# Ejecutar sincronización normal
python -m product_engine.main

# Usar base de datos test de Odoo
USE_TEST_ODOO=true python -m product_engine.main

# Forzar sincronización completa
FORCE_FULL_SYNC=true python -m product_engine.main

# Solo probar conexiones
TEST_CONNECTIONS_ONLY=true python -m product_engine.main

# Crear tabla de productos
python -m product_engine.database_updater
```

### Uso con Docker

```bash
# Desarrollo local
docker-compose -f deployment/docker-compose.local.yml up --build

# Producción
docker-compose -f deployment/docker-compose.prod.yml up -d
```

## 🌟 Funcionalidades Avanzadas

### Sincronización Incremental

El sistema automáticamente detecta la última fecha de sincronización y solo procesa productos modificados después de esa fecha:

```python
# El sistema usa el campo __last_update de Odoo
domain = [['__last_update', '>', last_sync_date]]
products_df = odoo_product.read_products(domain=domain)
```

### Generación de Embeddings

Los embeddings se generan automáticamente concatenando campos relevantes:

```python
# Ejemplo de texto para embedding
text = "SKU: PROD001. Name: Aceite de Coco Orgánico. Description: Aceite de coco virgen extra orgánico. Category: Aceites Naturales. Type: Product"

# Se genera embedding usando OpenAI
embedding = embedding_generator.generate([text])
```

### Búsquedas Vectoriales

Una vez que los embeddings están almacenados, puedes realizar búsquedas similares:

```sql
-- Buscar productos similares usando cosine similarity
SELECT sku, name, 1 - (embedding <=> query_embedding) as similarity
FROM products 
WHERE embedding IS NOT NULL
ORDER BY embedding <=> query_embedding
LIMIT 10;
```

## 🐳 Despliegue

### Configuración de Producción

1. **Preparar Secrets**:
```bash
# Ejecutar script de verificación
./deployment/scripts/pre_deploy_check.sh
```

2. **Desplegar**:
```bash
# Desplegar en Google Compute Engine
./deployment/scripts/deploy.sh
```

3. **Verificar**:
```bash
# Ver logs
gcloud compute ssh langgraph --zone=us-central1-c --command='cd /opt/product-engine && sudo docker-compose -f docker-compose.prod.yml logs -f'

# Estado del servicio
gcloud compute ssh langgraph --zone=us-central1-c --command='sudo systemctl status product-engine.timer'
```

### Programación Automática

El sistema se ejecuta automáticamente cada 4 horas usando systemd:

```bash
# Ver próximas ejecuciones
sudo systemctl list-timers product-engine.timer

# Ejecutar manualmente
sudo systemctl start product-engine.service
```

## 📊 Monitoreo y Logs

### Logs Estructurados

El sistema usa `structlog` para logging estructurado:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "info",
  "component": "products_sync_engine",
  "message": "Synchronization completed",
  "products_processed": 1250,
  "embeddings_generated": 45,
  "duration_seconds": 127.5
}
```

### Métricas de Rendimiento

Cada ejecución reporta métricas detalladas:

- Productos procesados
- Productos insertados/actualizados
- Productos desactivados
- Embeddings generados
- Duración total
- Errores encontrados

## 🔧 Desarrollo

### Estructura del Proyecto

```
product-engine/
├── src/
│   └── product_engine/
│       ├── __init__.py
│       ├── config.py
│       ├── odoo_api.py
│       ├── embedding_generator.py
│       ├── database_updater.py
│       └── main.py
├── deployment/
│   ├── Dockerfile
│   ├── docker-compose.local.yml
│   ├── docker-compose.prod.yml
│   ├── init-db.sql
│   ├── .dockerignore
│   └── scripts/
│       ├── deploy.sh
│       └── pre_deploy_check.sh
├── pyproject.toml
└── README.md
```

### Tests Locales

```bash
# Test de conexiones
TEST_CONNECTIONS_ONLY=true python -m product_engine.main

# Test con datos limitados
USE_TEST_ODOO=true python -m product_engine.main

# Sync completo local
ENVIRONMENT=local_machine python -m product_engine.main
```

## 🔒 Seguridad

- **Sin credenciales hardcodeadas**: Todo a través de variables de entorno o Secret Manager
- **Conexiones seguras**: Cloud SQL Proxy para acceso a base de datos
- **Usuario no-root**: Contenedores ejecutan con usuario limitado
- **Secrets rotation**: Soporte para rotación de credenciales

## ⚡ Optimizaciones

- **Operaciones en lote**: Inserts y updates masivos
- **Pools de conexión**: Reutilización de conexiones de base de datos
- **Rate limiting**: Control de llamadas a OpenAI API
- **Retry logic**: Reintentos automáticos con backoff exponencial
- **Índices optimizados**: Índices HNSW para búsquedas vectoriales eficientes

## 🤝 Contribución

1. Fork el repositorio
2. Crear rama feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -am 'Agregar nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

## 📄 Licencia

Este proyecto está bajo la licencia MIT. Ver `LICENSE` para más detalles.

## 📞 Soporte

Para soporte o preguntas:
- Email: bastian.miba@gmail.com
- Issues: [GitHub Issues](https://github.com/NotoriosTI/libraries/issues)

## 🔄 Changelog

### v0.1.0 (2024-01-15)
- ✨ Primera versión del sistema
- 🔄 Sincronización incremental desde Odoo
- 🤖 Generación automática de embeddings con OpenAI
- 🐳 Containerización completa
- ☁️ Despliegue en Google Cloud Platform
- 📊 Logging estructurado y métricas
