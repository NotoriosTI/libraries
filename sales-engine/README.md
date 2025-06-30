# Sales Engine

Motor de ventas para sincronización de datos entre Odoo y PostgreSQL.

## Descripción

Este proyecto sincroniza datos de ventas desde Odoo hacia una base de datos PostgreSQL en Google Cloud Platform, proporcionando una solución robusta para análisis de datos de ventas.

## Características

- ✅ Sincronización automática de datos de ventas desde Odoo producción
- ✅ Detección y prevención de duplicados
- ✅ Manejo robusto de errores y reintentos
- ✅ Logging estructurado con métricas
- ✅ Deployment automatizado en GCP
- ✅ Ejecución programada cada 6 horas

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
- ✅ **Ejecución inmediata de prueba** (verifica conectividad y sincronización)

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

## Mejoras Implementadas

Ver [MEJORAS_IMPLEMENTADAS.md](MEJORAS_IMPLEMENTADAS.md) para detalles de las mejoras recientes.

## Soporte

Para problemas o preguntas:
1. Revisar logs del deployment
2. Verificar estado de los servicios
3. Contactar al equipo de desarrollo
