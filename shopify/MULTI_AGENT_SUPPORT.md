# Soporte Multi-Agente para Librería Shopify

## 🎯 Objetivo

Esta actualización permite que la librería Shopify funcione con múltiples agentes (Emilia y Emma) sin romper la compatibilidad existente.

## 🔧 Cambios Realizados

### 1. Application Settings
- **GraphQLSettings**: Acepta parámetro `agent` para determinar qué configuración usar
- **StorefrontSettings**: Acepta parámetro `agent` para determinar qué configuración usar
- Mantiene instancias globales `settings` para compatibilidad hacia atrás
- Nuevas funciones `get_graphql_settings(agent)` y `get_storefront_settings(agent)`

### 2. Clases API Principales
Todas las clases ahora aceptan un parámetro opcional `agent`:
- `ShopifyAPI(agent="emilia")`
- `ShopifyOrders(agent="emilia")`
- `ShopifyProducts(agent="emilia")`
- `StorefrontAPI(agent="emilia")`
- `StorefrontSearch(agent="emilia")`

### 3. Configuración en config-manager
La librería utiliza las funciones existentes en config-manager:
- `secrets.get_shopify_config()` → Para Emilia
- `secrets.get_emma_shopify_config()` → Para Emma

## 📋 Variables de Entorno

### Emilia (existente)
```bash
EMILIA_SHOPIFY_SHOP_URL
EMILIA_SHOPIFY_TOKEN_API_ADMIN
EMILIA_SHOPIFY_TOKEN_API_STOREFRONT
EMILIA_SHOPIFY_API_VERSION
```

### Emma (nueva)
```bash
EMMA_SHOPIFY_SHOP_URL
EMMA_SHOPIFY_TOKEN_API_ADMIN
EMMA_SHOPIFY_TOKEN_API_STOREFRONT
EMMA_SHOPIFY_API_VERSION
```

## 🚀 Uso

### Código Existente de Emilia (SIN CAMBIOS)
```python
# Todo este código sigue funcionando igual
from shopify import ShopifyAPI, ShopifyOrders, ShopifyProducts
from shopify import StorefrontAPI, StorefrontSearch

api = ShopifyAPI()
orders = ShopifyOrders()
products = ShopifyProducts()
storefront = StorefrontAPI()
search = StorefrontSearch()
```

### Nuevo Código para Emma
```python
# Simplemente agregar agent="emma"
from shopify import ShopifyAPI, ShopifyOrders, ShopifyProducts
from shopify import StorefrontAPI, StorefrontSearch

api = ShopifyAPI(agent="emma")
orders = ShopifyOrders(agent="emma")
products = ShopifyProducts(agent="emma")
storefront = StorefrontAPI(agent="emma")
search = StorefrontSearch(agent="emma")
```

### Uso Mixto (Misma Aplicación)
```python
# Diferentes agentes en la misma aplicación
emilia_orders = ShopifyOrders()                    # Default a emilia
emma_products = ShopifyProducts(agent="emma")      # Emma
emilia_search = StorefrontSearch(agent="emilia")   # Emilia explícito
```

### Override Manual de Credenciales
```python
# Sigue funcionando igual que antes
api = ShopifyAPI(
    shop_url="custom-shop.myshopify.com",
    api_password="custom-token",
    agent="emma"  # Opcional
)
```

## ✅ Compatibilidad

### 100% Retrocompatible
- Todo el código existente de Emilia funciona sin cambios
- No se requieren modificaciones en proyectos existentes
- Las instancias globales `settings` se mantienen

### Valores por Defecto
- `agent` por defecto es `"emilia"`
- Si no se especifica `agent`, usa la configuración de Emilia
- Los mensajes de error se adaptan dinámicamente al agente

## 🔍 Estructura Interna

### Flujo de Configuración
1. Se recibe parámetro `agent` (default: "emilia")
2. Si `agent == "emma"` → usa `get_emma_shopify_config()`
3. Si `agent != "emma"` → usa `get_shopify_config()`
4. Se validan las credenciales requeridas
5. Se configuran las URLs y tokens correspondientes

### Manejo de Errores
Los errores de configuración muestran el prefijo correcto:
```
ValueError: EMMA_SHOPIFY_SHOP_URL no está configurado en config-manager
ValueError: EMILIA_SHOPIFY_TOKEN_API_ADMIN no está configurado en config-manager
```

## 🧪 Testing

Ejecutar el archivo de ejemplo:
```bash
cd shopify
python example_usage.py
```

Este archivo prueba:
- Compatibilidad con código existente de Emilia
- Nuevo soporte para Emma
- Uso mixto de ambos agentes
- Ejemplos de uso

## 📝 Notas Importantes

1. **No Breaking Changes**: El código existente funciona sin modificaciones
2. **Escalable**: Fácil agregar más agentes en el futuro
3. **Limpio**: Uso de config-manager centralizado
4. **Flexible**: Permite override manual de credenciales
5. **Consistente**: Mismo patrón en todas las clases
