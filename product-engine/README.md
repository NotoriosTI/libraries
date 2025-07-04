# Product Engine

Una librería robusta y automatizada para sincronizar el catálogo de productos desde Odoo a PostgreSQL con generación de embeddings vectoriales usando OpenAI. Diseñada con arquitectura modular para máxima eficiencia y escalabilidad.

## 🎯 Objetivo

Desarrollar una librería en Python que actúe como un motor de sincronización de datos entre un sistema ERP Odoo y una base de datos PostgreSQL alojada en Google Cloud SQL, enfocándose exclusivamente en el catálogo de productos y enriqueciendo cada producto con embeddings vectoriales para búsquedas avanzadas.

## ✨ Características Principales

- **🔄 Sincronización Incremental Inteligente**: Solo sincroniza productos nuevos o modificados (ahorro del 95-99%)
- **🧠 Embeddings Vectoriales**: Genera automáticamente embeddings usando OpenAI API
- **🔍 Búsqueda Híbrida**: Combina búsqueda exacta por SKU con búsqueda semántica
- **📊 Operaciones UPSERT**: Manejo inteligente de productos nuevos vs existentes
- **🏗️ Arquitectura Modular**: Componentes especializados para máxima eficiencia
- **⚡ Optimizado para Performance**: Operaciones en lote y consultas eficientes
- **🔧 Configuración Multi-Entorno**: Desarrollo local y producción en Google Cloud
- **🛡️ Manejo Robusto de Errores**: Logging estructurado y recuperación automática
- **🐳 Containerización**: Docker y Docker Compose listos para producción

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

## 📁 Estructura del Proyecto

```
product-engine/
├── src/
│   ├── common/                    # Componentes compartidos
│   │   ├── config.py             # Configuración centralizada
│   │   ├── database.py           # Conexiones a BD
│   │   ├── models.py             # Modelos de datos
│   │   └── embedding_generator.py # Generación de embeddings
│   ├── db_client/                 # Operaciones de lectura
│   │   ├── product_reader.py     # Lectura de productos
│   │   └── product_search.py     # Búsqueda semántica
│   ├── db_manager/                # Operaciones de escritura
│   │   ├── product_updater.py    # Actualización de productos
│   │   └── sync_manager.py       # Sincronización con Odoo
│   └── product_engine/            # API pública
│       └── __init__.py           # Punto de entrada
├── tests/                         # Suite de pruebas
│   ├── test_integration_odoo_db.py
│   ├── test_db_manager_complete.py
│   └── test_sku_duplicates.py
├── deployment/                    # Configuración de despliegue
│   ├── docker-compose.local.yml
│   ├── docker-compose.prod.yml
│   └── Dockerfile
└── pyproject.toml                 # Configuración del proyecto
```

## 🔄 Sincronización Incremental

### ¿Cómo funciona?

La librería utiliza una **estrategia de sincronización incremental inteligente** que evita descargar miles de productos innecesariamente:

1. **📅 Obtiene la fecha de última sincronización** desde la base de datos
2. **🔍 Crea un filtro Odoo** para productos modificados: `[['write_date', '>', última_fecha]]`
3. **📥 Descarga solo productos modificados** después de esa fecha
4. **🔄 Aplica estrategia UPSERT** para manejar productos nuevos vs existentes

### Escenarios de Sincronización

| Escenario | Productos Descargados | Frecuencia | Eficiencia |
|-----------|----------------------|------------|------------|
| 🚀 **Primera sincronización** | 10,000 (todos) | Una vez | 0% (necesario) |
| 📅 **Sincronización rutinaria** | 15-50 productos | 99% de las veces | 99.5% |
| 📈 **Día con muchos cambios** | 150-500 productos | Ocasional | 95% |
| 😴 **Sin cambios** | 0 productos | Frecuente | 100% |
| 🔧 **Forzar completa** | 10,000 (todos) | Solo manual | 0% |

### Código de Ejemplo

```python
# Sincronización normal (incremental)
results = sync_manager.run_sync()
# Solo descarga productos modificados desde la última sincronización

# Forzar sincronización completa
results = sync_manager.run_sync(force_full_sync=True)
# Descarga todos los productos (usar solo cuando sea necesario)
```

## 🔄 Manejo de Productos: Nuevos vs Existentes

### Estrategia UPSERT

La librería **no diferencia manualmente** entre productos nuevos y existentes. En su lugar, utiliza la estrategia **UPSERT** de PostgreSQL:

```sql
INSERT INTO products (sku, name, description, ...)
VALUES (?, ?, ?, ...)
ON CONFLICT (sku) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    list_price = EXCLUDED.list_price,
    last_update = EXCLUDED.last_update;
```

### Comportamiento con SKUs Duplicados

| Situación | Comportamiento | Resultado |
|-----------|---------------|-----------|
| 🆕 **SKU nuevo** | `INSERT` | Producto creado |
| 🔄 **SKU existente** | `UPDATE` | Producto actualizado |
| 📦 **Lote mixto** | `UPSERT` | Algunos INSERT, algunos UPDATE |
| ❌ **Sin cambios** | `UPDATE` | Sin modificaciones reales |

### Ventajas de esta estrategia:

✅ **Simplicidad**: No necesita lógica compleja de comparación
✅ **Eficiencia**: PostgreSQL optimiza automáticamente las operaciones
✅ **Robustez**: Maneja todos los casos edge automáticamente
✅ **Escalabilidad**: Funciona igual con 10 o 10,000 productos

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

# Base de Datos PostgreSQL para productos
PRODUCT_DB_HOST=127.0.0.1
PRODUCT_DB_PORT=5432
PRODUCT_DB_NAME=productdb
PRODUCT_DB_USER=automation_admin
PRODUCT_DB_PASSWORD=tu_password

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
gcloud secrets create PRODUCT_DB_HOST --data-file=-
gcloud secrets create PRODUCT_DB_PORT --data-file=-
gcloud secrets create PRODUCT_DB_NAME --data-file=-
gcloud secrets create PRODUCT_DB_USER --data-file=-
gcloud secrets create PRODUCT_DB_PASSWORD --data-file=-
gcloud secrets create OPENAI_API_KEY --data-file=-
```

## 💾 Esquema de Base de Datos

La tabla `products` se crea automáticamente con este esquema optimizado:

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

-- Índices optimizados para performance
CREATE INDEX idx_products_active ON products (is_active);
CREATE INDEX idx_products_category ON products (category_id);
CREATE INDEX idx_products_last_update ON products (last_update);
CREATE INDEX idx_products_embedding ON products USING hnsw (embedding vector_cosine_ops);
```

## 🔄 Uso

### Uso Básico con la Nueva Arquitectura

```python
from db_manager.sync_manager import SyncManager
from db_client.product_reader import ProductReader
from db_client.product_search import ProductSearchClient

# 1. Sincronización desde Odoo
sync_manager = SyncManager(use_test_odoo=False)
results = sync_manager.run_sync()

if results["success"]:
    print(f"✅ Sincronizados {results['products_processed']} productos")
    print(f"📊 Embeddings generados: {results['embeddings_generated']}")
else:
    print(f"❌ Error: {results['error']}")

# 2. Lectura de productos
reader = ProductReader()
products = reader.get_active_products(limit=10)
print(f"📦 Productos activos: {len(products)}")

# 3. Búsqueda semántica
search_client = ProductSearchClient()
results = search_client.search_products(
    query="aceite esencial de lavanda",
    limit=5,
    similarity_threshold=0.7
)
print(f"🔍 Resultados de búsqueda: {len(results)}")
```

### Línea de Comandos

```bash
# Ejecutar sincronización normal
poetry run python -m db_manager.sync_manager

# Usar base de datos test de Odoo
USE_TEST_ODOO=true poetry run python -m db_manager.sync_manager

# Forzar sincronización completa
FORCE_FULL_SYNC=true poetry run python -m db_manager.sync_manager

# Solo probar conexiones
TEST_CONNECTIONS_ONLY=true poetry run python -m db_manager.sync_manager
```

## 🔍 Búsqueda Avanzada

### Búsqueda Híbrida

La librería soporta búsqueda híbrida que combina:

1. **Búsqueda exacta por SKU** - Para consultas precisas
2. **Búsqueda semántica** - Para consultas en lenguaje natural

```python
from db_client.product_search import ProductSearchClient

search_client = ProductSearchClient()

# Búsqueda por SKU exacto
results = search_client.search_products("ABC-123")
# Retorna exactamente el producto con SKU "ABC-123"

# Búsqueda semántica
results = search_client.search_products(
    "aceite esencial para relajación",
    similarity_threshold=0.7
)
# Retorna productos similares usando embeddings vectoriales
```

### Tipos de Búsqueda Soportados

| Tipo | Ejemplo | Uso |
|------|---------|-----|
| 🎯 **SKU Exacto** | `"ABC-123"` | Búsqueda precisa |
| 🧠 **Semántica** | `"aceite de lavanda"` | Búsqueda inteligente |
| 🔤 **Por nombre** | `"Mica Frost"` | Búsqueda textual |
| 📂 **Por categoría** | `category_id=157` | Filtrado por categoría |

## 🧪 Testing

### Suite de Pruebas Completa

```bash
# Ejecutar todas las pruebas
poetry run pytest tests/

# Pruebas específicas
poetry run python -m tests.test_integration_odoo_db      # Integración Odoo → BD
poetry run python -m tests.test_db_manager_complete      # Suite completa
poetry run python -m tests.test_sku_duplicates           # Manejo de duplicados
```

### Pruebas Incluidas

1. **🔗 Integración Odoo → Database**
   - Extrae productos reales de Odoo
   - Los inserta en la base de datos
   - Verifica el mapeo correcto de campos

2. **🔧 Funcionalidad Completa**
   - Operaciones de lectura (ProductReader)
   - Generación de embeddings
   - Búsqueda semántica
   - Búsqueda híbrida
   - Operaciones CRUD

3. **🔄 Manejo de SKUs Duplicados**
   - Inserción inicial
   - Actualización de productos existentes
   - Lotes mixtos (nuevos + existentes)
   - Verificación de integridad

## 📊 Flujo de Sincronización Detallado

```
┌─────────────────┐
│ Inicio Sync     │
└─────────┬───────┘
          │
          ▼
┌─────────────────┐    ┌─────────────────┐
│ ¿Primera vez?   │───►│ Sync Completa   │
└─────────┬───────┘    └─────────────────┘
          │
          ▼
┌─────────────────┐
│ Obtener última  │
│ fecha sync      │
└─────────┬───────┘
          │
          ▼
┌─────────────────┐
│ Crear domain    │
│ Odoo incremental│
└─────────┬───────┘
          │
          ▼
┌─────────────────┐    ┌─────────────────┐
│ Consultar       │───►│ ¿Productos      │
│ productos       │    │ encontrados?    │
└─────────────────┘    └─────────┬───────┘
                                 │
                                 ▼
                       ┌─────────────────┐
                       │ Mapear campos   │
                       │ Odoo → BD       │
                       └─────────┬───────┘
                                 │
                                 ▼
                       ┌─────────────────┐
                       │ Ejecutar UPSERT │
                       │ (bulk operation)│
                       └─────────┬───────┘
                                 │
                                 ▼
                       ┌─────────────────┐
                       │ Generar         │
                       │ embeddings      │
                       └─────────┬───────┘
                                 │
                                 ▼
                       ┌─────────────────┐
                       │ Finalizar sync  │
                       └─────────────────┘
```

## ⚡ Optimizaciones de Performance

### Operaciones en Lote

- **Bulk INSERT/UPDATE**: Usa `execute_values` para operaciones masivas
- **Tabla temporal**: Estrategia UPSERT optimizada con tabla temporal
- **Índices especializados**: Índices HNSW para búsqueda vectorial

### Gestión de Memoria

- **Procesamiento por lotes**: Evita cargar todos los productos en memoria
- **Conexiones eficientes**: Pool de conexiones para PostgreSQL
- **Límites configurables**: Control de memoria en generación de embeddings

## 🚨 Troubleshooting

### Problemas Comunes

1. **Error de conexión a Odoo**
   ```bash
   # Verificar credenciales
   poetry run python -c "from db_manager.sync_manager import SyncManager; SyncManager().test_connections()"
   ```

2. **Extensión pgvector no instalada**
   ```sql
   -- Instalar en PostgreSQL
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

3. **Productos sin embeddings**
   ```python
   # Forzar regeneración de embeddings
   from db_manager.product_updater import ProductUpdater
   updater = ProductUpdater()
   products = updater.get_products_needing_embeddings()
   print(f"Productos sin embeddings: {len(products)}")
   ```

### Logs y Debugging

```bash
# Habilitar logs detallados
export LOG_LEVEL=DEBUG
poetry run python -m db_manager.sync_manager

# Verificar estado de la base de datos
poetry run python -c "
from common.database import database
result = database.execute_query('SELECT COUNT(*) as count FROM products WHERE embedding IS NULL')
print(f'Productos sin embeddings: {result[0][\"count\"]}')
"
```

## 📈 Monitoreo y Métricas

### Métricas de Sincronización

```python
results = sync_manager.run_sync()
print(f"""
📊 Métricas de Sincronización:
- Productos procesados: {results['products_processed']}
- Productos actualizados: {results['products_upserted']}
- Productos desactivados: {results['products_deactivated']}
- Embeddings generados: {results['embeddings_generated']}
- Duración: {results['duration_seconds']:.2f}s
""")
```

### Métricas de Base de Datos

```sql
-- Estado general de productos
SELECT 
    COUNT(*) as total_productos,
    COUNT(CASE WHEN is_active THEN 1 END) as activos,
    COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as con_embeddings
FROM products;

-- Productos por categoría
SELECT category_name, COUNT(*) as cantidad
FROM products 
WHERE is_active = true
GROUP BY category_name
ORDER BY cantidad DESC;
```

## 🤝 Contribución

### Desarrollo

```bash
# Configurar entorno de desarrollo
git clone https://github.com/NotoriosTI/libraries.git
cd libraries/product-engine
poetry install

# Ejecutar tests
poetry run pytest tests/

# Ejecutar linting
poetry run flake8 src/
poetry run black src/
```

### Estructura de Commits

```
feat: añadir nueva funcionalidad
fix: corregir bug
docs: actualizar documentación
test: añadir o modificar tests
refactor: refactorizar código
```

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo `LICENSE` para más detalles.

## 🔗 Enlaces Relacionados

- [Librería config-manager](../config-manager/)
- [Librería odoo-api](../odoo-api/)
- [Documentación pgvector](https://github.com/pgvector/pgvector)
- [API OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings)

## 📞 Soporte

Para preguntas o soporte técnico:

- **Issues**: [GitHub Issues](https://github.com/NotoriosTI/libraries/issues)
- **Documentación**: Este README y comentarios en el código
- **Tests**: Revisar la suite de pruebas para ejemplos de uso
