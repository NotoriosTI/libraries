# Shopify Library

Librería Python para interactuar con las APIs de Shopify.

## 🆕 Cambios Recientes

### ✅ Configuración Mejorada
- **Variables Extra Permitidas**: La librería ya no falla si tienes otras variables en tu `.env`
- **Validación No Estricta**: Solo valida las variables que realmente necesita
- **Nombres de Variables Estandarizados**: Usa los nombres que ya tienes en tu `.env`

### 🔧 Variables de Entorno

#### Para Storefront API (Módulo Principal)
```bash
# (*) OBLIGATORIO
SHOPIFY_SHOP_URL=tu-tienda.myshopify.com
SHOPIFY_TOKEN_API_STOREFRONT=tu-token-de-storefront

# OPCIONAL
SHOPIFY_API_VERSION=2025-01
```

#### Para Admin API (Opcional - Módulo separado)
```bash
# Solo si usas el módulo admin
SHOPIFY_TOKEN_API_ADMIN=tu-token-de-admin
```

## 📚 Módulos

### Storefront API
```python
from shopify.storefront import StorefrontSearch

# Búsqueda de productos
search = StorefrontSearch()
results = search.search_products(["aceite", "esencia"])
```

### Admin API
```python
from shopify.admin import ShopifyProducts, ShopifyOrders

# Gestión de productos
products = ShopifyProducts()
all_products = products.read_all_products()

# Gestión de órdenes
orders = ShopifyOrders()
all_orders = orders.read_all_orders()
```

## 🚀 Instalación

```bash
# Desde el directorio del proyecto
pip install -e .

# O usando poetry
poetry install
```

## 🔍 Características

- ✅ **GraphQL First**: Usa GraphQL para mejor rendimiento
- ✅ **Paginación Automática**: Maneja automáticamente grandes volúmenes de datos
- ✅ **Manejo de Errores**: Mensajes claros y manejo robusto de errores
- ✅ **Configuración Flexible**: Permite variables extra en `.env` sin problemas
- ✅ **Compatibilidad**: Mantiene compatibilidad con APIs REST existentes

## 📝 Notas

- **Variables Extra**: La librería ignora variables en tu `.env` que no necesita
- **Configuración Mínima**: Solo necesitas configurar las variables obligatorias para usar Storefront API
- **Admin API**: Opcional, solo si planeas usar funcionalidades administrativas
- **Módulos Separados**: Storefront y Admin tienen configuraciones independientes
