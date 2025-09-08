-- ============================================================================
-- REFACTORIZACIÓN COMPLETA DE FORECAST: MIGRACIÓN DE BASE DE DATOS
-- ============================================================================
-- 
-- Esta migración elimina completamente las tablas existentes y reconstruye
-- la tabla forecast desde cero con la nueva estructura simplificada:
-- - sku, year, month (clave primaria)
-- - max_monthly_sales (máximo histórico de ventas)
-- - current_stock (inventario actual desde Odoo)
-- - forecasted_qty (cantidad pronosticada)
-- - required_production (cantidad a producir)
-- - priority (BAJA, MEDIA, ALTA, CRITICO)
-- - created_at, updated_at (timestamps)
-- ============================================================================

-- ============================================================================
-- PASO 1: RESPALDAR DATOS EXISTENTES
-- ============================================================================

-- Crear tabla de respaldo si la tabla forecast existe
DO $$ 
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'forecast') THEN
        DROP TABLE IF EXISTS forecast_backup;
        CREATE TABLE forecast_backup AS SELECT * FROM forecast;
        RAISE NOTICE 'Backup de tabla forecast creado en forecast_backup';
    ELSE
        RAISE NOTICE 'Tabla forecast no existe, no se requiere backup';
    END IF;
END $$;

-- Crear tabla de respaldo de production_forecast si existe
DO $$ 
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'production_forecast') THEN
        DROP TABLE IF EXISTS production_forecast_backup;
        CREATE TABLE production_forecast_backup AS SELECT * FROM production_forecast;
        RAISE NOTICE 'Backup de tabla production_forecast creado en production_forecast_backup';
    ELSE
        RAISE NOTICE 'Tabla production_forecast no existe, no se requiere backup';
    END IF;
END $$;

-- ============================================================================
-- PASO 2: ELIMINAR TABLAS EXISTENTES COMPLETAMENTE
-- ============================================================================

-- Eliminar ambas tablas completamente
DROP TABLE IF EXISTS forecast CASCADE;
DROP TABLE IF EXISTS production_forecast CASCADE;

RAISE NOTICE 'Tablas forecast y production_forecast eliminadas completamente';

-- ============================================================================
-- PASO 3: CREAR NUEVA TABLA FORECAST DESDE CERO
-- ============================================================================

-- Crear la nueva tabla forecast con estructura optimizada
CREATE TABLE forecast (
    sku VARCHAR(50) NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    max_monthly_sales INTEGER NOT NULL DEFAULT 0,
    current_stock DECIMAL(10,2) NOT NULL DEFAULT 0,
    forecasted_qty INTEGER NOT NULL DEFAULT 0,
    required_production INTEGER NOT NULL DEFAULT 0,
    unit_price DECIMAL(10,2) NOT NULL DEFAULT 0,
    priority VARCHAR(10) NOT NULL DEFAULT 'BAJA' 
        CHECK (priority IN ('BAJA', 'MEDIA', 'ALTA', 'CRITICO')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Clave primaria compuesta
    CONSTRAINT forecast_pkey PRIMARY KEY (sku, year, month),
    
    -- Constraints adicionales
    CONSTRAINT forecast_year_check CHECK (year >= 2020 AND year <= 2030),
    CONSTRAINT forecast_month_check CHECK (month >= 1 AND month <= 12),
    CONSTRAINT forecast_quantities_check CHECK (
        max_monthly_sales >= 0 AND 
        current_stock >= 0 AND 
        forecasted_qty >= 0 AND 
        required_production >= 0 AND
        unit_price >= 0
    )
);

-- ============================================================================
-- PASO 4: CREAR ÍNDICES OPTIMIZADOS
-- ============================================================================

-- Crear índices optimizados para la nueva estructura
CREATE INDEX idx_forecast_sku ON forecast (sku);
CREATE INDEX idx_forecast_year_month ON forecast (year, month);
CREATE INDEX idx_forecast_priority ON forecast (priority);
CREATE INDEX idx_forecast_required_production ON forecast (required_production DESC);
CREATE INDEX idx_forecast_unit_price ON forecast (unit_price DESC);
CREATE INDEX idx_forecast_created_at ON forecast (created_at);
CREATE INDEX idx_forecast_updated_at ON forecast (updated_at);
CREATE INDEX idx_forecast_priority_production ON forecast (priority, required_production DESC);
CREATE INDEX idx_forecast_current_month ON forecast (year, month) WHERE year = EXTRACT(YEAR FROM CURRENT_DATE) AND month = EXTRACT(MONTH FROM CURRENT_DATE);

-- ============================================================================
-- PASO 5: CREAR FUNCIÓN TRIGGER PARA UPDATED_AT
-- ============================================================================

-- Crear función trigger para updated_at (puede no existir)
CREATE OR REPLACE FUNCTION update_forecast_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Crear trigger para actualizar updated_at automáticamente
CREATE TRIGGER update_forecast_updated_at
    BEFORE UPDATE ON forecast
    FOR EACH ROW EXECUTE FUNCTION update_forecast_updated_at_column();

-- ============================================================================
-- PASO 6: FUNCIONES AUXILIARES PARA CÁLCULOS
-- ============================================================================

-- Crear función para obtener máximo de ventas históricas por SKU por mes
CREATE OR REPLACE FUNCTION calculate_max_monthly_sales(sku_param VARCHAR(50))
RETURNS INTEGER AS $$
DECLARE
    max_sales INTEGER;
BEGIN
    SELECT COALESCE(MAX(monthly_total), 0) INTO max_sales
    FROM (
        SELECT 
            items_product_sku,
            EXTRACT(YEAR FROM issueddate) as year,
            EXTRACT(MONTH FROM issueddate) as month,
            SUM(items_quantity) as monthly_total
        FROM sales_items 
        WHERE items_product_sku = sku_param
            AND items_quantity > 0
            AND issueddate >= CURRENT_DATE - INTERVAL '24 months'  -- Últimos 2 años
            AND (sales_channel IS NULL OR sales_channel != 'Cotizaciones')
        GROUP BY items_product_sku, EXTRACT(YEAR FROM issueddate), EXTRACT(MONTH FROM issueddate)
    ) AS monthly_sales;
    
    RETURN COALESCE(max_sales, 0);
END;
$$ LANGUAGE plpgsql;

-- Función para obtener el precio unitario más reciente por SKU
CREATE OR REPLACE FUNCTION get_latest_unit_price(sku_param VARCHAR(50))
RETURNS DECIMAL(10,2) AS $$
DECLARE
    latest_price DECIMAL(10,2);
BEGIN
    -- Obtener el precio unitario de la venta más reciente
    SELECT COALESCE(items_unitprice, 0) INTO latest_price
    FROM sales_items 
    WHERE items_product_sku = sku_param
        AND items_quantity > 0
        AND items_unitprice > 0
        AND (sales_channel IS NULL OR sales_channel != 'Cotizaciones')
    ORDER BY issueddate DESC
    LIMIT 1;
    
    -- Si no hay precio reciente, obtener promedio de los últimos 6 meses
    IF latest_price IS NULL OR latest_price = 0 THEN
        SELECT COALESCE(AVG(items_unitprice), 0) INTO latest_price
        FROM sales_items 
        WHERE items_product_sku = sku_param
            AND items_quantity > 0
            AND items_unitprice > 0
            AND issueddate >= CURRENT_DATE - INTERVAL '6 months'
            AND (sales_channel IS NULL OR sales_channel != 'Cotizaciones');
    END IF;
    
    RETURN COALESCE(latest_price, 0);
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- PASO 7: FUNCIÓN PARA DETERMINAR PRIORIDAD
-- ============================================================================

-- Función para calcular prioridad basada en heurísticas de rotación
CREATE OR REPLACE FUNCTION calculate_priority(
    forecasted_qty_param INTEGER,
    current_stock_param DECIMAL(10,2),
    max_monthly_sales_param INTEGER
)
RETURNS VARCHAR(10) AS $$
DECLARE
    rotation_threshold INTEGER := 50; -- Umbral para distinguir alta/baja rotación
    stock_ratio DECIMAL;
BEGIN
    -- Determinar si es producto de alta o baja rotación
    IF max_monthly_sales_param >= rotation_threshold THEN
        -- PRODUCTO DE ALTA ROTACIÓN: usar porcentaje stock/forecast
        IF forecasted_qty_param > 0 THEN
            stock_ratio := current_stock_param / forecasted_qty_param;
            
            IF stock_ratio >= 0.50 THEN
                RETURN 'CRITICO';
            ELSIF stock_ratio >= 0.35 THEN
                RETURN 'ALTA';
            ELSIF stock_ratio >= 0.20 THEN
                RETURN 'MEDIA';
            ELSE
                RETURN 'BAJA';
            END IF;
        ELSE
            RETURN 'BAJA';
        END IF;
    ELSE
        -- PRODUCTO DE BAJA ROTACIÓN: usar valores fijos de required_production
        DECLARE
            required_prod INTEGER := LEAST(forecasted_qty_param, max_monthly_sales_param) - CAST(current_stock_param AS INTEGER);
        BEGIN
            IF required_prod >= 40 THEN
                RETURN 'CRITICO';
            ELSIF required_prod >= 25 THEN
                RETURN 'ALTA';
            ELSIF required_prod >= 10 THEN
                RETURN 'MEDIA';
            ELSE
                RETURN 'BAJA';
            END IF;
        END;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- PASO 8: FUNCIÓN PARA VALIDAR VENTAS EN ÚLTIMOS 12 MESES
-- ============================================================================

-- Función para verificar si un SKU tuvo ventas en los últimos 12 meses
CREATE OR REPLACE FUNCTION has_sales_last_12_months(sku_param VARCHAR(50))
RETURNS BOOLEAN AS $$
DECLARE
    sales_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO sales_count
    FROM sales_items 
    WHERE items_product_sku = sku_param
        AND items_quantity > 0
        AND issueddate >= CURRENT_DATE - INTERVAL '12 months'
        AND (sales_channel IS NULL OR sales_channel != 'Cotizaciones');
    
    RETURN sales_count > 0;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- PASO 9: FUNCIÓN PARA VERIFICAR SI ES MATERIA PRIMA
-- ============================================================================

-- Función para verificar si un SKU es materia prima (se debe filtrar)
CREATE OR REPLACE FUNCTION is_raw_material(sku_param VARCHAR(50))
RETURNS BOOLEAN AS $$
BEGIN
    -- Implementar lógica para identificar materias primas
    -- Por ejemplo, si el SKU o descripción contiene "MP" o patrones específicos
    RETURN (
        SELECT COUNT(*) > 0
        FROM sales_items 
        WHERE items_product_sku = sku_param
            AND (
                UPPER(items_product_description) LIKE '%MP%' OR
                UPPER(items_product_description) LIKE '%MATERIA PRIMA%' OR
                UPPER(items_product_description) LIKE '%RAW MATERIAL%'
            )
        LIMIT 1
    );
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- VERIFICACIÓN POST-MIGRACIÓN
-- ============================================================================

-- Verificar estructura final de la nueva tabla forecast
\echo 'Verificando estructura de la nueva tabla forecast:'
SELECT column_name, data_type, is_nullable, column_default 
FROM information_schema.columns 
WHERE table_name = 'forecast' 
ORDER BY ordinal_position;

-- Verificar índices creados
\echo 'Verificando índices creados:'
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'forecast'
ORDER BY indexname;

-- Verificar constraints y triggers
\echo 'Verificando constraints:'
SELECT constraint_name, constraint_type 
FROM information_schema.table_constraints 
WHERE table_name = 'forecast';

-- Verificar funciones auxiliares creadas
\echo 'Verificando funciones auxiliares:'
SELECT routine_name, routine_type 
FROM information_schema.routines 
WHERE routine_name IN (
    'calculate_max_monthly_sales', 
    'get_latest_unit_price',
    'calculate_priority', 
    'has_sales_last_12_months',
    'is_raw_material',
    'update_forecast_updated_at_column'
) ORDER BY routine_name;

-- Verificar triggers
\echo 'Verificando triggers:'
SELECT trigger_name, event_manipulation, action_timing 
FROM information_schema.triggers 
WHERE event_object_table = 'forecast';

-- Mostrar tablas de backup creadas
\echo 'Tablas de backup disponibles:'
SELECT table_name 
FROM information_schema.tables 
WHERE table_name LIKE '%backup%' 
ORDER BY table_name;

-- ============================================================================
-- CONFIRMACIÓN DE MIGRACIÓN EXITOSA
-- ============================================================================

\echo '============================================================================'
\echo 'MIGRACIÓN COMPLETADA EXITOSAMENTE'
\echo '============================================================================'
\echo ''
\echo 'Cambios aplicados:'
\echo '1. ✅ Backup de datos existentes creado'
\echo '2. ✅ Tablas forecast y production_forecast eliminadas'
\echo '3. ✅ Nueva tabla forecast creada con estructura optimizada'
\echo '4. ✅ Índices optimizados creados'
\echo '5. ✅ Funciones auxiliares implementadas'
\echo '6. ✅ Triggers configurados'
\echo ''
\echo 'Estructura nueva tabla forecast:'
\echo '- sku, year, month (clave primaria)'
\echo '- max_monthly_sales, current_stock, forecasted_qty'
\echo '- required_production, unit_price, priority'
\echo '- created_at, updated_at'
\echo ''
\echo 'Próximos pasos:'
\echo '1. Ejecutar pipeline refactorizado para generar nuevos forecasts'
\echo '2. Verificar funcionamiento con: run_pipeline()'
\echo '3. En caso de problemas, usar rollback commands abajo'
\echo '============================================================================'

-- ============================================================================
-- COMANDOS DE ROLLBACK (EN CASO DE EMERGENCIA)
-- ============================================================================

-- Para rollback completo en caso de emergencia, ejecutar:
-- DROP TABLE IF EXISTS forecast CASCADE;
-- DROP FUNCTION IF EXISTS calculate_max_monthly_sales CASCADE;
-- DROP FUNCTION IF EXISTS get_latest_unit_price CASCADE;
-- DROP FUNCTION IF EXISTS calculate_priority CASCADE;
-- DROP FUNCTION IF EXISTS has_sales_last_12_months CASCADE;
-- DROP FUNCTION IF EXISTS is_raw_material CASCADE;
-- DROP FUNCTION IF EXISTS update_forecast_updated_at_column CASCADE;
-- 
-- -- Restaurar tabla forecast original (si existe backup)
-- ALTER TABLE forecast_backup RENAME TO forecast;
-- 
-- -- Restaurar tabla production_forecast (si existe backup)
-- ALTER TABLE production_forecast_backup RENAME TO production_forecast;
