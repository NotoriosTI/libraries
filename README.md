# Libraries Monorepo
Herramientas y dependencias comunes para agentes y servicios de datos.

## Módulos

- `config-manager`: Configuración centralizada y secretos (GCP Secret Manager/.env)
- `dev-utils`: Utilidades (logger bonito, pydantic partial update)
- `odoo-api`: Cliente de alto nivel para Odoo (XML-RPC)
- `odoo-engine`: Ingesta desde Odoo a PostgreSQL + embeddings
- `product-engine`: Sincronización y búsqueda híbrida de productos (pgvector + OpenAI)
- `sales-engine`: Sincronización de ventas y forecasting
- `shopify`: Cliente Storefront/Admin (GraphQL/REST) con config centralizada
- `slack-api`: Bot/cliente Slack (Socket Mode, audio→texto opcional)
- `whatsapp`: Cliente HTTP para WhatsApp

## Requisitos

- Python 3.12+ (algunos módulos requieren 3.13)
- Poetry

## Instalación local rápida

```bash
# Ejemplo: instalar un módulo editable
pip install -e dev-utils/
pip install -e config-manager/
```

## Configuración

Los módulos usan `config-manager` cuando aplica. Para desarrollo local, crea `.env` en la raíz del módulo que lo requiera. En producción, usar `ENVIRONMENT=production` y secretos en Google Secret Manager.

## Licencia

MIT
