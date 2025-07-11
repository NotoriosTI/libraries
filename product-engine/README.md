# Product Engine

Este repositorio contiene la librería `product-engine`, una herramienta de Python diseñada para sincronizar productos desde un sistema ERP Odoo a una base de datos PostgreSQL, enriquecerlos con embeddings vectoriales usando OpenAI, y habilitar capacidades de búsqueda híbrida (semántica y de texto completo).

-----

## 🌟 Visión General

El objetivo principal de `product-engine` es crear y mantener una base de datos de productos optimizada para búsquedas inteligentes. Esto permite a las aplicaciones realizar consultas que entienden el significado y la intención del usuario, en lugar de solo coincidir con palabras clave exactas.

**Características Principales:**

  - **Sincronización con Odoo**: Extrae datos de productos directamente desde la API de Odoo.
  - **Enriquecimiento con IA**: Genera embeddings vectoriales para los nombres y descripciones de los productos utilizando los modelos de OpenAI.
  - **Base de Datos Potenciada**: Almacena los productos en PostgreSQL utilizando la extensión `pgvector` para soportar búsquedas vectoriales.
  - **Búsqueda Híbrida**: Ofrece una función de búsqueda que combina la búsqueda semántica (por similitud de embeddings) con la búsqueda tradicional de texto completo (por SKU o palabras clave), proporcionando resultados más relevantes.

-----

## 🚀 Instalación con Poetry

Para añadir `product-engine` como una dependencia en tu proyecto gestionado con Poetry, ejecuta el siguiente comando. Esto asegurará que la librería y sus dependencias se instalen correctamente desde este repositorio de Git.

```bash
poetry add git+https://github.com/NotoriosTI/libraries.git#product-db --subdirectory product-engine
```

Este comando añadirá la siguiente línea a tu archivo `pyproject.toml`:

```toml
[tool.poetry.dependencies]
product-engine = {git = "https://github.com/NotoriosTI/libraries.git", rev = "product-db", subdirectory = "product-engine"}
```

-----

## ⚙️ Configuración

La configuración de la librería se gestiona a través de `config-manager`, que carga las variables de entorno necesarias. Debes crear un archivo `.env` en la raíz de tu proyecto.

**Variables de Entorno Requeridas:**

```ini
# Entorno de ejecución: local_machine, local_container, o production
ENVIRONMENT=local_machine

# Credenciales de la base de datos de Odoo (producción)
ODOO_URL=https://tu-dominio-odoo.com
ODOO_DB=tu_base_de_datos
ODOO_USERNAME=tu_usuario
ODOO_PASSWORD=tu_contraseña

# Credenciales de la base de datos de Odoo (test)
TEST_ODOO_URL=https://tu-dominio-odoo-test.com
TEST_ODOO_DB=tu_base_de_datos_test
TEST_ODOO_USERNAME=tu_usuario_test
TEST_ODOO_PASSWORD=tu_contraseña_test

# Credenciales de la base de datos de Destino (PostgreSQL)
PRODUCT_DB_HOST=localhost
PRODUCT_DB_PORT=5432
PRODUCT_DB_NAME=productdb
PRODUCT_DB_USER=user
PRODUCT_DB_PASSWORD=password

# Clave de la API de OpenAI
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

-----

## 🎮 Uso de la Librería

El uso se divide en dos operaciones principales: sincronizar los productos y buscarlos.

### 1\. Sincronización de Productos

El `SyncManager` orquesta todo el proceso de extracción, transformación y carga (ETL).

```python
from product_engine import SyncManager

# Inicializa el gestor de sincronización.
# use_test_odoo=True usará las credenciales de TEST_ODOO_*
sync_manager = SyncManager(use_test_odoo=False)

# Ejecuta la sincronización completa.
# Esto leerá desde Odoo, generará embeddings y guardará en PostgreSQL.
sync_manager.run_sync()

print("Sincronización completada.")
```

### 2\. Búsqueda de Productos

La función `search_products` permite realizar consultas híbridas.

```python
from product_engine import search_products

# Realiza una búsqueda semántica.
query = "aceite para masajes relajantes"
results = search_products(query=query, limit=5)

# Imprime los resultados
print(f"Resultados para la búsqueda: '{query}'")
for product in results:
    print(
        f"- SKU: {product['sku']}, "
        f"Nombre: {product['name']}, "
        f"Score de Relevancia: {product['relevance_score']:.4f}"
    )
```

-----

## 🧪 Pruebas y Validación

La librería cuenta con una suite de pruebas robusta para garantizar la fiabilidad, integridad y correctitud de cada componente.

### Objetivo General de las Pruebas

El propósito principal es validar el flujo de datos de extremo a extremo (desde la extracción en Odoo hasta la búsqueda en PostgreSQL) y verificar la lógica de negocio individual de cada módulo. Se utilizan *mocks* extensivamente para aislar los tests de servicios externos y garantizar ejecuciones rápidas y predecibles.

### Tipos de Pruebas Disponibles

Las pruebas están organizadas en dos categorías principales:

1.  **Pruebas de la Librería (`tests/library`)**: Se centran en la lógica interna y las integraciones clave de la librería.

      - `test_integration_odoo_db.py`: **Test de Integración Principal**. Simula el flujo completo: extrae datos de un Odoo mockeado, los procesa, y verifica que se inserten correctamente en una base de datos de prueba. Es crucial para validar el pipeline ETL.
      - `test_search.py`: Valida que la función de **búsqueda híbrida** construya las consultas SQL apropiadas, combine los resultados de la búsqueda vectorial y de texto completo, y devuelva el formato esperado.
      - `test_similarity_filter.py`: Prueba específicamente el componente de **filtrado por similitud**, asegurando que el cálculo de la relevancia y el umbral de corte funcionen correctamente.
      - `test_sku_duplicates.py`: Garantiza la **integridad de los datos** verificando que el sistema maneje correctamente los SKUs duplicados durante la sincronización, evitando inconsistencias.
      - `test_new_structure.py` y `test_new_structure_simple.py`: Pruebas que validan la **arquitectura modular** de la librería, asegurando que los componentes como `SyncManager`, `ProductUpdater` y `ProductReader` interactúen de la forma esperada.

2.  **Pruebas de Despliegue (`tests/deployment`)**: Verifican que la configuración para el despliegue en contenedores sea correcta.

      - `test_deploy.sh`: Un script que prueba el ciclo de vida del despliegue en un entorno controlado, incluyendo la construcción de las imágenes de Docker y la ejecución de los servicios definidos en `docker-compose.test.yml`.

### ¿Cómo Ejecutar las Pruebas?

Para ejecutar la suite de pruebas de la librería, asegúrate de haber instalado las dependencias de desarrollo con Poetry.

```bash
# Instala todas las dependencias, incluyendo las de desarrollo
poetry install

# Ejecuta la suite de pruebas de la librería desde la raíz del monorepo
poetry run pytest product-engine/tests/library/
```