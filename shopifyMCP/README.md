# lib_shopify_core

Librería de infraestructura pura y agnóstica para interactuar con la API de Shopify (GraphQL).

Diseñada para ser el motor de conexión robusto detrás de agentes de IA, sistemas ERP o scripts de automatización. Mantiene una separación estricta entre **Admin API** (Backend/Gestión) y **Storefront API** (Frontend/Venta), priorizando siempre el rendimiento y la limpieza de datos.

## 🚀 Filosofía

1.  **Infrastructure-First:** No contiene lógica de negocio compleja ni agentes. Solo entrega los datos crudos o limpios que tu aplicación necesita.
2.  **Configuración Explícita:** Nada de `load_dotenv` oculto. Tú pasas las credenciales, tú controlas el entorno.
3.  **GraphQL Nativo:** Abstrae la complejidad de las queries de GraphQL, manejando IDs globales (`gid://`) y paginación interna, entregando diccionarios Python limpios.

## 📦 Instalación

Esta librería utiliza **Poetry** para la gestión de dependencias.

```bash
# Si estás desarrollando la librería
poetry install

# Si vas a usarla en otro proyecto (ej. Agente LangGraph)
poetry add git+[https://github.com/tu-org/lib_shopify_core.git](https://github.com/tu-org/lib_shopify_core.git)

```

### Dependencias Principales

* `requests`: Para llamadas HTTP síncronas y estables.
* `beautifulsoup4`: Para limpiar el HTML "sucio" de las descripciones de Shopify antes de que llegue a tu IA.

## 🛠 Guía de Uso Rápido

### 1. Admin API (Gestión de Productos y Pedidos)

Ideal para agentes que necesitan acceso total ("La verdad del negocio").

```python
from shopify_core.admin.client import ShopifyAdminClient
from shopify_core.admin.products import ShopifyProductManager

# 1. Inicialización Explícita (Sin variables de entorno ocultas)
client = ShopifyAdminClient(
    shop_url="[https://mi-tienda.myshopify.com](https://mi-tienda.myshopify.com)",
    admin_token="shpat_xxxxxxxxxxxxxxxxxxxxxxxx",  # Tu token Admin
    api_version="2025-01"
)

manager = ShopifyProductManager(client)

# CASO A: Búsqueda Inteligente (Soporta sintaxis de búsqueda Shopify)
# Ideal para input de usuario o LLMs
resultados = manager.search_products("title:zapatos AND tag:verano", limit=3)

for p in resultados:
    print(f"[{p['status']}] {p['title']} - Stock: {p['stock_total']}")
    # Output: [ACTIVE] Zapatos Deportivos - Stock: 150

# CASO B: Ficha Técnica Completa (Por ID o SKU)
# Detecta automáticamente si pasas un ID numérico o un SKU
ficha = manager.read_product_info("ZAP-001")  # o "8492812312"

if ficha:
    print(f"Descripción limpia: {ficha['description'][:100]}...")
    print(f"Variantes: {len(ficha['variants'])}")

```

### 2. Storefront API (Vista de Cliente)

Útil solo si necesitas simular lo que ve un cliente anónimo en la web.

```python
from shopify_core.storefront.client import ShopifyStorefrontClient

client = ShopifyStorefrontClient(
    shop_url="[https://mi-tienda.myshopify.com](https://mi-tienda.myshopify.com)",
    storefront_token="shpublic_xxxxxxxxxxxx"
)

# Ejecución de queries crudas para casos de uso específicos de frontend
data = client.execute("""
    query { shop { name } }
""")

```

## 🏗 Estructura del Proyecto

```text
shopifyMCP/
├── src/
│   └── shopify/
│       ├── admin/          # Lógica de Backend (Full Access)
│       │   ├── client.py   # Manejo de Auth y Rate Limits
│       │   └── products.py # Funciones consolidadas (search/read)
│       ├── storefront/     # Lógica de Frontend (Limited Access)
│       │   └── client.py
│       └── utils.py        # Limpieza de HTML y GIDs
├── pyproject.toml
└── README.md

```

## 🧪 Pruebas (Roadmap)

Para ejecutar los tests (una vez implementados):

```bash
poetry run pytest

```

---

**Author:** Notorio STI
**License:** Proprietary
