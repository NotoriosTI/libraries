# Sales Engine

Motor de ventas y pronósticos para sincronización de datos desde Odoo hacia PostgreSQL y generación de stock necesario para producción.

## Descripción

Este proyecto:
- Sincroniza datos de ventas desde Odoo hacia una base de datos PostgreSQL en Google Cloud Platform.
- Genera pronósticos de ventas por SKU y el stock necesario de producción comparando el forecast con el inventario disponible en Odoo.

## Características

- ✅ Sincronización automática de datos de ventas desde Odoo producción
- ✅ Detección y prevención de duplicados
- ✅ Manejo robusto de errores y reintentos
- ✅ Logging estructurado con métricas
- ✅ Generación de pronósticos de ventas por SKU (12 meses) y persistencia en tabla `forecast`
- ✅ Cálculo de stock necesario para producción por mes objetivo y persistencia en tabla `production_forecast`
- ✅ Priorización (ALTA/MEDIA/BAJA) basada en brecha Forecast − Inventario
- ✅ Deployment automatizado en GCP y ejecución programada cada 6 horas
- ✅ **Proxy compartido con Product Engine** para conexión a base de datos

## Cómo funciona (alto nivel)

1. Se sincronizan ventas a `sales_items` (incremental por `updated_at`).
2. Se generan forecasts por SKU (serie futura) y se guardan en `forecast` (con índices y upsert).
3. Se calcula el stock necesario para el mes objetivo: `production_needed = forecast_mes − inventory_odoo` y se guarda en `production_forecast`.
4. Se asigna prioridad (ALTA/MEDIA/BAJA) en función de la magnitud de la brecha.

## 🔗 Proxy Compartido

**IMPORTANTE**: Sales Engine ahora usa el **proxy compartido** con Product Engine para conectarse a la base de datos. Esto significa:

- ✅ **Un solo proxy** para ambos servicios
- ✅ **Sin conflictos de puertos** 
- ✅ **Mejor gestión de recursos**
- ✅ **Configuración simplificada**

### Gestión del Proxy Compartido

```bash
# Verificar estado del proxy compartido
./deployment/scripts/manage_shared_proxy.sh status

# Iniciar proxy compartido (si no está corriendo)
./deployment/scripts/manage_shared_proxy.sh start

# Ver logs del proxy
./deployment/scripts/manage_shared_proxy.sh logs

# Reiniciar proxy
./deployment/scripts/manage_shared_proxy.sh restart
```

### Configuración de Conexión

Sales Engine ahora se conecta a la base de datos usando:
- **Host**: `127.0.0.1` (localhost)
- **Puerto**: `5432`
- **Red**: `host` (acceso directo al proxy compartido)

## 🚀 Deployment a Producción

### Prerequisitos

Antes de ejecutar el deployment, asegúrate de que tienes:

1. **Google Cloud CLI instalado y autenticado**
   ```bash
   gcloud auth login
   gcloud config set project notorios
   ```

2. **VM `langgraph` configurada en GCP**
   - La VM debe existir en la zona `us-central1-c`
   - Debe tener Docker y docker-compose instalados
   - Debe tener acceso a Google Container Registry

3. **Cloud SQL instance configurada**
   - **IMPORTANTE**: Debes actualizar el nombre real de tu instancia de Cloud SQL
   - Edita `deployment/scripts/deploy.sh` línea 11:
     ```bash
     INSTANCE_NAME="tu-instancia-cloud-sql-real"  # Reemplaza con el nombre real
     ```

4. **Secrets configurados en Secret Manager**
   Los siguientes secrets deben estar configurados en Google Cloud Secret Manager:
   ```
   ODOO_PROD_URL
   ODOO_PROD_DB
   ODOO_PROD_USERNAME
   ODOO_PROD_PASSWORD
   DB_HOST
   DB_PORT
   DB_NAME
   DB_USER
   DB_PASSWORD
   ```

### ⚠️ VERIFICACIONES PRE-DEPLOY

**CRÍTICO**: Antes de hacer deploy, completa estos pasos:

1. **Actualiza el nombre de la instancia Cloud SQL**:
   ```bash
   # Edita deployment/scripts/deploy.sh línea 11
   INSTANCE_NAME="nombre-real-de-tu-instancia"
   ```

2. **Verifica la configuración de Odoo**:
   - ✅ El sistema está configurado para usar `odoo_prod` por defecto
   - ✅ Variable `USE_TEST_ODOO=false` en docker-compose.prod.yml
   - ✅ Todos los datos se extraerán de la base de datos de producción de Odoo

3. **Verifica que la VM existe**:
   ```bash
   gcloud compute instances describe langgraph --zone=us-central1-c
   ```

4. **Verifica que los secrets existen**:
   ```bash
   gcloud secrets list | grep -E "(ODOO_PROD|DB_)"
   ```

### Ejecutar Deployment

Una vez completadas las verificaciones:

```bash
cd sales-engine
chmod +x deployment/scripts/deploy.sh
./deployment/scripts/deploy.sh
```

El script realizará automáticamente:
- ✅ Verificación de prerequisitos
- ✅ Build y push de la imagen Docker
- ✅ Deployment en la VM
- ✅ Configuración del scheduler (cada 6 horas)
- ✅ Verificación del estado de los servicios
- ✅ **Ejecución inmediata de prueba** (verifica conectividad, sincronización y generación de forecasts)

### Comandos Útiles Post-Deploy

```bash
# Ver logs en tiempo real
gcloud compute ssh langgraph --zone=us-central1-c --command='cd /opt/sales-engine && docker-compose -f docker-compose.prod.yml logs -f'

# Verificar estado de servicios
gcloud compute ssh langgraph --zone=us-central1-c --command='cd /opt/sales-engine && docker-compose -f docker-compose.prod.yml ps'

# Ejecutar manualmente (adicional a la prueba del deployment)
gcloud compute ssh langgraph --zone=us-central1-c --command='cd /opt/sales-engine && docker-compose -f docker-compose.prod.yml run --rm sales-engine'

# Verificar timer del sistema
gcloud compute ssh langgraph --zone=us-central1-c --command='sudo systemctl status sales-engine.timer'
```

### ⏰ Ejecución y Scheduling

**Después del deployment:**
1. **Se ejecuta automáticamente una prueba** para verificar que todo funciona
2. **Se configura el scheduler** para ejecución automática cada 6 horas:
   - 00:00 (medianoche)
   - 06:00 (madrugada) 
   - 12:00 (mediodía)
   - 18:00 (tarde)

**Para ejecuciones adicionales:**
- Usa el comando de "Ejecutar manualmente" arriba
- O espera a la próxima ejecución programada

## Modos de ejecución y variables de entorno

La imagen/servicio soporta los siguientes modos mediante variables de entorno:

- `USE_TEST_ODOO` (default `false`): usa Odoo test si es `true`.
- `FORCE_FULL_SYNC` (default `false`): fuerza sincronización completa de ventas.
- `TEST_CONNECTIONS_ONLY` (default `false`): solo prueba conexiones.
- `SKIP_FORECAST` (default `false`): si `true`, omite el pipeline de pronóstico y producción.
- `FORECAST_ONLY` (default `false`): ejecuta solo el pipeline de pronóstico y producción (sin sincronización de ventas).

Ejemplos (local con Poetry):

```bash
# Sync ventas + forecasts (default)
poetry run run-updater

# Solo sync de ventas (sin forecasts)
SKIP_FORECAST=true poetry run run-updater

# Solo pipeline de pronóstico + producción (sin sync de ventas)
FORECAST_ONLY=true poetry run run-updater

# Probar conexiones
TEST_CONNECTIONS_ONLY=true poetry run run-updater
```

Ejemplos (en VM con script de ejecución):

```bash
# Sync + forecasts (default)
./deployment/scripts/run_sales_engine.sh

# Solo probar conexiones
./deployment/scripts/run_sales_engine.sh test

# Forzar sync completa + forecasts
./deployment/scripts/run_sales_engine.sh full-sync

# Solo pipeline de pronóstico
./deployment/scripts/run_sales_engine.sh forecast-only

# Sync sin forecasts
./deployment/scripts/run_sales_engine.sh --skip-forecast
```

## CLI alternativa de pronósticos (reportes CSV o DB)

Para generar únicamente los forecasts (sincronización aparte) también puedes usar el módulo dedicado:

```bash
# Guardar en base de datos (tabla forecast)
python -m sales_engine.forecaster.generate_all_forecasts --mode db

# Exportar archivos CSV a data/forecasts/
python -m sales_engine.forecaster.generate_all_forecasts --mode report
```

Salidas principales:
- Tabla `forecast` con registros mensuales por SKU (clave `sku, forecast_date`).
- Archivos CSV en `data/forecasts/` cuando se usa `--mode report`.

## Consultas rápidas

Ejemplos útiles en PostgreSQL:

```sql
-- Forecast del mes objetivo (ejemplo: octubre 2024)
SELECT sku, forecast_date, forecasted_quantity
FROM forecast
WHERE year = 2024 AND month = 10
ORDER BY forecasted_quantity DESC
LIMIT 20;

-- Productos con mayor necesidad de producción del mes actual
SELECT sku, product_name, production_needed, priority
FROM production_forecast
WHERE year = EXTRACT(YEAR FROM CURRENT_DATE)
  AND month = EXTRACT(MONTH FROM CURRENT_DATE)
  AND production_needed > 0
ORDER BY production_needed DESC
LIMIT 20;
```

## Desarrollo Local

### Instalación

```bash
# Instalar dependencias
poetry install

# Configurar variables de entorno
cp .env.example .env  # Editar con tus credenciales
```

### Ejecutar localmente

```bash
# Ejecutar el updater
poetry run run-updater

# Ejecutar tests
poetry run pytest
```

Tips:
- Los modos descritos arriba también aplican localmente exportando variables de entorno.
- Para inspeccionar resultados, consulta tablas `sales_items`, `forecast` y `production_forecast`.

## Arquitectura

```
Odoo (Producción) → Sales Engine → PostgreSQL (GCP)
                      ↓
                 Google Cloud Logging
```

## Configuración

El sistema utiliza diferentes configuraciones según el entorno:

- **Producción**: Secrets desde Google Cloud Secret Manager
- **Local**: Variables desde archivo `.env`

Tablas gestionadas automáticamente (creación/índices/upsert):
- `sales_items` (sincronización de ventas)
- `forecast` (series futuras por SKU con estadísticas por SKU)
- `production_forecast` (brecha Forecast − Inventario por mes, con prioridad)

## Mejoras Implementadas

Ver [MEJORAS_IMPLEMENTADAS.md](MEJORAS_IMPLEMENTADAS.md) para detalles de las mejoras recientes.

## Soporte

Para problemas o preguntas:
1. Revisar logs del deployment
2. Verificar estado de los servicios
3. Contactar al equipo de desarrollo
