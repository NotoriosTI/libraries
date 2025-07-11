-- Initialize database for Product Engine development
-- This script is run when the PostgreSQL container starts for the first time

-- Create the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create a test user for development
-- In production, credentials are managed via Secret Manager
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'product_user') THEN
        CREATE USER product_user WITH PASSWORD 'product_password';
    END IF;
END
$$;

-- Grant necessary permissions
GRANT ALL PRIVILEGES ON DATABASE products_db TO product_user;
GRANT ALL ON SCHEMA public TO product_user;

-- Log successful initialization
SELECT 'Product Engine database initialized successfully' AS status; 