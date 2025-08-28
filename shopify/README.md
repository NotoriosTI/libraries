# Shopify Library

Librería Python para interactuar con las APIs de Shopify de manera eficiente y robusta.

## 🚀 Características Principales

- ✅ **GraphQL First**: Usa GraphQL para mejor rendimiento y flexibilidad
- ✅ **Paginación Automática**: Maneja automáticamente grandes volúmenes de datos
- ✅ **Manejo de Errores**: Mensajes claros y manejo robusto de errores
- ✅ **Configuración Flexible**: Permite variables extra en `.env` sin problemas
- ✅ **Compatibilidad**: Mantiene compatibilidad con APIs REST existentes
- ✅ **Búsqueda Avanzada**: Búsqueda de productos con múltiples términos y filtros

## 📦 Instalación

```bash
# Desde el directorio del proyecto
pip install -e .

# O usando poetry
poetry install
```

## 🔧 Configuración

### Variables de Entorno

#### Para Storefront API (Módulo Principal)
```bash
# (*) OBLIGATORIO
SHOPIFY_SHOP_URL=tu-tienda.myshopify.com
SHOPIFY_TOKEN_API_STOREFRONT=tu-token-de-storefront

# OPCIONAL
SHOPIFY_API_VERSION=2025-01
```

#### Para Admin API (GraphQL - Módulo separado)
```bash
# Solo si usas el módulo GraphQL admin
SHOPIFY_PASSWORD=tu-admin-access-token
```

## 📚 Módulos y Uso

### Storefront API - Búsqueda de Productos

```python
from shopify.storefront import StorefrontSearch

# Inicializar búsqueda
search = StorefrontSearch()

# Búsqueda básica con múltiples términos
search_terms = ["vainilla", "dulce", "jabón"]
results = search.search_products(search_terms, limit_per_term=5)

# Búsqueda consolidada (productos + variantes)
consolidated = search.search_products_consolidated(search_terms, limit_per_term=3)

# Búsqueda con filtros específicos
filtered_results = search.search_products(
    ["aceite esencial"], 
    limit_per_term=10,
    product_types=["aceite", "esencia"]
)
```

### Admin API - Gestión de Productos

```python
from shopify.graphql import ShopifyProducts

# Inicializar gestor de productos
products = ShopifyProducts()

# Obtener todos los productos
all_products = products.read_all_products()

# Obtener productos con filtros
filtered_products = products.read_products(
    product_types=["aceite", "esencia"],
    status="active"
)

# Crear nuevo producto
new_product = products.create_product({
    "title": "Aceite de Lavanda",
    "product_type": "aceite esencial",
    "vendor": "Mi Tienda",
    "tags": ["natural", "relajante"]
})
```

### Admin API - Gestión de Órdenes

```python
from shopify.graphql import ShopifyOrders

# Inicializar gestor de órdenes
orders = ShopifyOrders()

# Obtener todas las órdenes
all_orders = orders.read_all_orders()

# Obtener órdenes por estado
pending_orders = orders.read_orders(status="open")
fulfilled_orders = orders.read_orders(status="fulfilled")

# Obtener órdenes por fecha
recent_orders = orders.read_orders(
    created_at_min="2024-01-01",
    created_at_max="2024-12-31"
)
```

## 🔍 Casos de Uso Comunes

### 1. Búsqueda de Productos para SEO
```python
from shopify.storefront import StorefrontSearch

search = StorefrontSearch()

# Búsqueda para optimización SEO
seo_terms = ["aceite esencial", "esencia natural", "aromaterapia"]
seo_results = search.search_products_consolidated(seo_terms, limit_per_term=20)

# Analizar resultados para SEO
for product in seo_results:
    print(f"Producto: {product['title']}")
    print(f"SKU: {product['variant_sku']}")
    print(f"Precio: {product['variant_price']}")
    print(f"Inventario: {product['variant_inventory_quantity']}")
    print("---")
```

### 2. Gestión de Inventario
```python
from shopify.graphql import ShopifyProducts

products = ShopifyProducts()

# Obtener productos con bajo inventario
low_stock = products.read_products(
    inventory_quantity_min=0,
    inventory_quantity_max=10
)

# Actualizar inventario
for product in low_stock:
    print(f"Producto con bajo stock: {product['title']}")
    print(f"Stock actual: {product['total_inventory']}")
```

### 3. Análisis de Ventas
```python
from shopify.graphql import ShopifyOrders

orders = ShopifyOrders()

# Obtener órdenes del mes actual
import datetime
now = datetime.datetime.now()
month_start = now.replace(day=1).strftime("%Y-%m-%d")

monthly_orders = orders.read_orders(
    created_at_min=month_start,
    status="any"
)

# Calcular métricas
total_orders = len(monthly_orders)
total_revenue = sum(float(order['total_price']) for order in monthly_orders)

print(f"Órdenes del mes: {total_orders}")
print(f"Revenue total: ${total_revenue:.2f}")
```

## 🆕 Cambios Recientes

### ✅ Configuración Mejorada
- **Variables Extra Permitidas**: La librería ya no falla si tienes otras variables en tu `.env`
- **Validación No Estricta**: Solo valida las variables que realmente necesita
- **Nombres de Variables Estandarizados**: Usa los nombres que ya tienes en tu `.env`

## 📝 Notas Importantes

- **Variables Extra**: La librería ignora variables en tu `.env` que no necesita
- **Configuración Mínima**: Solo necesitas configurar las variables obligatorias para usar Storefront API
- **Admin API**: Opcional, solo si planeas usar funcionalidades administrativas
- **Módulos Separados**: Storefront y Admin tienen configuraciones independientes
- **Rate Limiting**: La librería maneja automáticamente los límites de API de Shopify

## 🧪 Testing

```bash
# Ejecutar tests básicos
cd shopify
python tests/test.py

# O usando poetry
poetry run python tests/test.py
```

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo `LICENSE` para más detalles.

## 🤝 Contribuir

Las contribuciones son bienvenidas. Por favor, abre un issue o pull request para sugerencias o mejoras.
