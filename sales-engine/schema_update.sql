-- Schema updates for sales_items table to support proper upserts and tracking

-- Step 1: Add composite primary key
-- This ensures each invoice-item combination is unique
ALTER TABLE sales_items 
ADD CONSTRAINT sales_items_pkey 
PRIMARY KEY (salesinvoiceid, items_product_sku);

-- Step 2: Add timestamp columns for tracking
ALTER TABLE sales_items
ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;

-- Step 3: Create trigger function for automatic updated_at updates
CREATE OR REPLACE FUNCTION update_sales_items_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Step 4: Create trigger that automatically updates updated_at on row modification
DROP TRIGGER IF EXISTS update_sales_items_updated_at ON sales_items;
CREATE TRIGGER update_sales_items_updated_at
    BEFORE UPDATE ON sales_items
    FOR EACH ROW EXECUTE FUNCTION update_sales_items_updated_at_column();

-- Step 5: Create additional indexes for performance (if they don't exist)
CREATE INDEX IF NOT EXISTS idx_sales_items_created_at ON sales_items (created_at);
CREATE INDEX IF NOT EXISTS idx_sales_items_updated_at ON sales_items (updated_at);
CREATE INDEX IF NOT EXISTS idx_sales_items_customer ON sales_items (customer_customerid);
CREATE INDEX IF NOT EXISTS idx_sales_items_salesman ON sales_items (salesman_name);

-- Step 6: Update existing rows to have proper timestamps (for existing data)
UPDATE sales_items 
SET created_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP 
WHERE created_at IS NULL OR updated_at IS NULL;

-- Verification queries
SELECT 'Schema update completed successfully' as status;
SELECT 'Primary key constraint: ' || conname as constraint_info 
FROM pg_constraint 
WHERE conrelid = 'sales_items'::regclass AND contype = 'p';

SELECT 'Trigger created: ' || tgname as trigger_info 
FROM pg_trigger 
WHERE tgrelid = 'sales_items'::regclass;