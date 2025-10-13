# Nueva Arquitectura de Config Manager

## Resumen

La nueva arquitectura de `config-manager` introduce un sistema modular y controlado para la gestión de secretos y configuraciones, reemplazando el enfoque monolítico anterior basado en una sola clase `Settings`. Esta nueva implementación utiliza Pydantic para validación de datos y permite una gestión más granular y mantenible de las configuraciones por servicio.

## Criterios de Implementación

### 1. **Modularidad por Servicio**
- Cada servicio (Emma, Emilia, Juan) tiene su propio archivo de configuración
- Separación clara de responsabilidades entre servicios
- Configuraciones específicas por dominio de aplicación

### 2. **Clase Base `Secret`**
- Clase abstracta que maneja la lógica común de carga de secretos
- Soporte automático para entornos `local_machine` y `production`
- Integración transparente con Google Cloud Secret Manager y variables de entorno

### 3. **Validación con Pydantic**
- Validación automática de tipos de datos
- Aliases para nombres de variables de entorno
- Manejo robusto de errores y valores faltantes

### 4. **Compatibilidad Multi-Entorno**
- Detección automática del entorno (`ENVIRONMENT` env var)
- Carga desde `.env` en desarrollo local
- Carga desde GCP Secret Manager en producción

## Estructura de Archivos

```
src/config_manager/
├── common.py          # Clase base Secret y configuraciones compartidas
├── emma.py           # Configuraciones específicas de Emma
├── emilia.py         # Configuraciones específicas de Emilia  
├── juan.py           # Configuraciones específicas de Juan
└── __init__.py       # Exports centralizados
```

## Implementación para el Agente Emma

### 1. **Configuraciones Compartidas (common.py)**

Para configuraciones que Emma comparte con otros servicios:

```python
from config_manager.common import Secret, LangSmithSecret, OdooProductionSecret

# Ejemplo de uso de configuraciones compartidas
langsmith = LangSmithSecret()
odoo_prod = OdooProductionSecret()
```

**Configuraciones disponibles en common.py:**
- `LangSmithSecret`: API key y proyecto de LangSmith
- `OdooProductionSecret`: Configuración de Odoo producción
- `OdooTestSecret`: Configuración de Odoo testing

### 2. **Configuraciones Específicas de Emma (emma.py)**

Para configuraciones exclusivas del agente Emma:

```python
from config_manager.emma import (
    OpenAISecret,
    EmmaDBSecret, 
    GoogleDocsSecret,
    ServiceAccountSecret,
    ShopifyAPISecret,
    ChatwootSecret,
    LocalCredentialSecret
)

# Ejemplo de uso
openai_config = OpenAISecret()
db_config = EmmaDBSecret()
shopify_config = ShopifyAPISecret()
```

**Configuraciones específicas de Emma:**
- `OpenAISecret`: API key de OpenAI
- `EmmaDBSecret`: Base de datos principal de Emma
- `GoogleDocsSecret`: IDs de documentos de Google
- `ServiceAccountSecret`: Email de cuenta de servicio
- `ShopifyAPISecret`: Configuración completa de Shopify
- `ChatwootSecret`: Configuración de Chatwoot
- `LocalCredentialSecret`: Ruta de credenciales locales

## Guía de Implementación

### Paso 1: Importar las Configuraciones Necesarias

```python
# Para configuraciones compartidas
from config_manager.common import LangSmithSecret, OdooProductionSecret

# Para configuraciones específicas de Emma
from config_manager.emma import (
    OpenAISecret,
    EmmaDBSecret,
    ShopifyAPISecret,
    ChatwootSecret
)
```

### Paso 2: Inicializar las Configuraciones

```python
# Inicialización básica
openai_secret = OpenAISecret()
db_secret = EmmaDBSecret()
shopify_secret = ShopifyAPISecret()
chatwoot_secret = ChatwootSecret()
```

### Paso 3: Acceder a los Valores

```python
# Los valores se cargan automáticamente según el entorno
api_key = openai_secret.api_key
db_host = db_secret.host
db_name = db_secret.name
shop_url = shopify_secret.url
admin_token = shopify_secret.admin_token
```

### Paso 4: Manejo de Errores

```python
try:
    openai_secret = OpenAISecret()
    print(f"OpenAI API Key: {openai_secret.api_key}")
except KeyError as e:
    print(f"Variable de entorno faltante: {e}")
except ValueError as e:
    print(f"Error de validación: {e}")
```

## Variables de Entorno Requeridas

### Para Desarrollo Local (.env)
```bash
ENVIRONMENT=local_machine

# Emma específicas
EMMA_OPENAI_API_KEY=sk-...
EMMA_DB_HOST=localhost
EMMA_DB_NAME=emmadb
EMMA_DB_USER=user
EMMA_DB_PASSWORD=password
EMMA_DB_PORT=5432

# Google Docs
EMMA_DOCS_SALES_ID=doc_id_here
EMMA_DOCS_SUMMARY_ID=doc_id_here

# Shopify
EMMA_SHOPIFY_SHOP_URL=https://shop.myshopify.com
EMMA_SHOPIFY_TOKEN_API_ADMIN=shpat_...
EMMA_SHOPIFY_TOKEN_API_STOREFRONT=shpat_...
EMMA_SHOPIFY_API_VERSION=2025-01

# Chatwoot
EMMA_CHATWOOT_BASE_URL=https://app.chatwoot.com
EMMA_CHATWOOT_ACCOUNT_ID=123
EMMA_CHATWOOT_TOKEN=token_here

# Credenciales locales
EMMA_CREDENTIALS_PATH=/path/to/credentials.json
```

### Para Producción
```bash
ENVIRONMENT=production
GCP_PROJECT_ID=your-project-id

# Las mismas variables pero almacenadas en GCP Secret Manager
# con los mismos nombres de alias definidos en las clases
```

## Ventajas de la Nueva Arquitectura

1. **Modularidad**: Cada servicio maneja sus propias configuraciones
2. **Mantenibilidad**: Cambios en un servicio no afectan otros
3. **Validación**: Pydantic asegura tipos de datos correctos
4. **Flexibilidad**: Fácil agregar nuevas configuraciones
5. **Debugging**: Errores más específicos y localizables
6. **Testing**: Configuraciones aisladas para testing

## Migración desde la Arquitectura Anterior

### Antes (settings.py)
```python
from config_manager.settings import secrets
db_config = secrets.get_emma_database_config()
```

### Ahora (nueva arquitectura)
```python
from config_manager.emma import EmmaDBSecret
db_secret = EmmaDBSecret()
# Acceso directo a propiedades
host = db_secret.host
name = db_secret.name
```

## Consideraciones Importantes

1. **Compatibilidad**: La nueva arquitectura coexiste con la anterior durante la transición
2. **Performance**: Carga lazy de secretos desde GCP solo cuando se necesitan
3. **Seguridad**: Validación automática de tipos y valores requeridos
4. **Documentación**: Cada clase documenta claramente sus campos y aliases

Esta nueva arquitectura proporciona una base sólida y escalable para la gestión de configuraciones en el ecosistema de servicios, especialmente optimizada para el agente Emma y sus necesidades específicas.
