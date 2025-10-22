from odoo_engine.utils import get_pg_dsn, OdooClient
from sqlalchemy import create_engine, text
import pandas as pd
import google.cloud.bigquery as bq
from dev_utils import PrettyLogger

pd.set_option('display.max_columns', None)

class SaleOrderManager:
    """Class to manage sale order operations including supplier data, missing products, and components"""

    def __init__(self, product_codes=None):
        """Initialize the SaleOrderManager with product codes"""
        self.logger = PrettyLogger("sale-order-manager")
        self.client = bq.Client()
        self.product_codes = product_codes or [
    "MP100",
    "MP014",
    "MP029"
]
        self._build_product_codes_string()
        self._supplier_data = None
        self._products_info = None
        self._missing_products = None
        self._missing_components = None
        self.odoo_client = OdooClient()

    def _build_product_codes_string(self):
        """Build the formatted string of product codes for SQL queries"""
        self.default_codes_str = "("
        for i, code in enumerate(self.product_codes):
            if i == len(self.product_codes) - 1:
                self.default_codes_str += f"'{code}'"
            else:
                self.default_codes_str += f"'{code}', "
        self.default_codes_str += ")"

    @property
    def supplier_data_query(self):
        """SQL query to get supplier data from Odoo"""
        return """
WITH price_data AS (
    SELECT 
        p.odoo_id AS product_id,
        p.name AS product_name,
        p.default_code AS product_default_code,
        prt.id AS supplier_id,
        prt.name AS supplier_name,
        prt.rut AS supplier_vat,
        pol.unit_price,
        po.date_order,
        ROW_NUMBER() OVER (
            PARTITION BY p.odoo_id, prt.id
            ORDER BY po.date_order DESC NULLS LAST, pol.write_date DESC NULLS LAST
        ) AS rn
    FROM product p
    JOIN purchase_order_line pol 
        ON pol.product_id = p.id
    JOIN purchase_order po 
        ON po.id = pol.order_id
    JOIN partner prt 
        ON prt.id = po.partner_id
    WHERE prt.supplier_rank > 0
      AND p.default_code IS NOT NULL
)
SELECT 
    product_id,
    product_name,
    product_default_code,
    supplier_id,
    supplier_name,
    supplier_vat,
    MIN(unit_price) AS min_price,
    MAX(unit_price) AS max_price,
    AVG(unit_price) AS avg_price,
    MAX(CASE WHEN rn = 1 THEN unit_price END) AS last_price
FROM price_data
GROUP BY product_id, product_name, product_default_code, supplier_id, supplier_name, supplier_vat
ORDER BY product_default_code, supplier_name;
"""

    def get_products_info(self):
        """Get product information from Odoo database"""
        if self._products_info is None:
            dsn = get_pg_dsn()
            engine = create_engine(dsn, echo=False, future=True)
            query = """
            SELECT
                id as product_id,
                name as product_name,
                default_code
            FROM product
            WHERE default_code IS NOT NULL
            """
            with engine.connect() as conn:
                result = conn.execute(text(query))
                self._products_info = pd.DataFrame(result)
        return self._products_info

    def get_missing_products(self):
        """Get missing products from BigQuery"""
        if self._missing_products is None:
            query = """
            SELECT
                product_id,
                CAST(required_quantity AS FLOAT64) as required_quantity,
                CAST(on_hand_quantity AS FLOAT64) as on_hand_qty,
                priority,
                forecast_month
            FROM sales_analytics.product_missing_current_month
            WHERE priority != 'BAJA' AND CAST(required_quantity AS FLOAT64) > 0
            """
            result = self.client.query_and_wait(query)
            self._missing_products = result.to_dataframe()
        return self._missing_products

    def get_missing_components(self):
        """Get missing components from BigQuery"""
        if self._missing_components is None:
            query = """
            SELECT
                component_product_id,
                CAST(required_to_order AS FLOAT64) as required_to_order,
                CAST(on_hand_component_qty AS FLOAT64) as on_hand_component_qty,
                priority,
                forecast_month
            FROM sales_analytics.required_component_orders_current_month
            WHERE CAST(required_to_order AS FLOAT64) > 0
            """
            result = self.client.query_and_wait(query)
            self._missing_components = result.to_dataframe()
        return self._missing_components

    def get_supplier_data(self):
        """Get supplier data from Odoo database"""
        if self._supplier_data is None:
            dsn = get_pg_dsn()
            engine = create_engine(dsn, echo=False, future=True)
            with engine.connect() as conn:
                result = conn.execute(text(self.supplier_data_query.format(self.default_codes_str)))
                self._supplier_data = pd.DataFrame(result)
        self.logger.info(f"Supplier data shape: {self._supplier_data.shape}")
        print(self._supplier_data.head())
        return self._supplier_data

    def get_missing_products_report(self):
        """Get and display missing products report"""
        products_df = self.get_products_info()
        self.logger.loading("Fetching missing products from BigQuery")
        missing_products = self.get_missing_products()
        self.logger.info(f"Missing products shape: {missing_products.shape}")

        if not missing_products.empty:
            missing_products_enriched = missing_products.merge(
                products_df,
                left_on='product_id',
                right_on='product_id',
                how='left'
            )

            self.logger.info("Missing products (enriched with product info)")
            missing_products_sorted = missing_products_enriched.sort_values("priority")
            print(missing_products_sorted[[
                'product_id', 'product_name', 'default_code', 'priority', 'required_quantity',
                'on_hand_qty', 'forecast_month'
            ]])

        return missing_products_enriched if not missing_products.empty else pd.DataFrame()

    def get_missing_components_report(self):
        """Get and display missing components report"""
        products_df = self.get_products_info()
        self.logger.loading("Fetching missing components from BigQuery")
        missing_components = self.get_missing_components()
        self.logger.info(f"Missing components shape: {missing_components.shape}")

        if not missing_components.empty:
            missing_components_enriched = missing_components.merge(
                products_df,
                left_on='component_product_id',
                right_on='product_id',
                how='left'
            )

            self.logger.info("Missing components (enriched with product info)")
            missing_components_sorted = missing_components_enriched.sort_values("priority")
            print(missing_components_sorted[[
                'component_product_id', 'product_name', 'default_code', 'priority', 'required_to_order',
                'on_hand_component_qty', 'forecast_month'
            ]])

        return missing_components_enriched if not missing_components.empty else pd.DataFrame()

    def get_missing_components_final_df(self):
        """Get final dataframe for missing components with supplier information"""
        # Get missing components data
        missing_components = self.get_missing_components()
        if missing_components.empty:
            return pd.DataFrame()

        # Get products info
        products_df = self.get_products_info()

        # Get supplier data
        supplier_df = self.get_supplier_data()

        # Join missing components with products
        missing_components_enriched = missing_components.merge(
            products_df,
            left_on='component_product_id',
            right_on='product_id',
            how='left'
        )

        # Join with supplier data on product_id
        final_df = missing_components_enriched.merge(
            supplier_df,
            left_on='component_product_id',
            right_on='product_id',
            how='left',
            suffixes=('', '_supplier')
        )

        # Filter out rows with no supplier information
        # Check for supplier columns (they should have '_supplier' suffix)
        supplier_cols = [col for col in final_df.columns if col.endswith('_supplier')]

        if supplier_cols:
            # Drop rows where the first supplier column is NaN
            final_df = final_df.dropna(subset=[supplier_cols[0]])
            self.logger.info(f"Dropped rows without supplier info. Remaining: {len(final_df)} rows")

        if final_df.empty:
            self.logger.info("No missing components with supplier information found")
            return pd.DataFrame()

        # Format avg_price with max 3 decimals and handle problematic values
        def format_avg_price(price_val):
            try:
                # Handle None/NaN values
                if price_val is None or (isinstance(price_val, float) and (price_val != price_val)):  # NaN check
                    return '0.000'

                # Convert to string for easier pattern matching
                price_str = str(price_val).strip()

                # Handle problematic values like "0E-20", "0.0E-20", very small numbers
                if 'E-' in price_str:
                    # Check if it's effectively zero (exponent <= -10)
                    try:
                        float_val = float(price_str)
                        if float_val == 0.0 or abs(float_val) < 1e-10:
                            return '0.000'
                    except:
                        return '0.000'

                # Handle zero values
                if price_str in ['0', '0.0', '0.00', '0E-20', '0.0E-20']:
                    return '0.000'

                # Convert to float
                price_float = float(price_str)

                # Handle negative values and very small numbers
                if price_float <= 0:
                    return '0.000'

                # Format with max 3 decimals
                return f"{price_float:.3f}"

            except (ValueError, TypeError, AttributeError):
                return '0.000'

        # Create final dataframe with specified columns
        result_df = pd.DataFrame({
            'id': final_df['component_product_id'].astype(str),
            'product_id': final_df['product_id'].astype(str),
            'product_name': final_df['product_name'].str[:15],
            'default_code': final_df['default_code'].astype(str),
            'on_hand_qty': final_df['on_hand_component_qty'].astype(str),
            'required_qty': final_df['required_to_order'].astype(str),
            'supplier_id': final_df['supplier_id'].astype(str),
            'supplier_name': final_df['supplier_name'].str[:15],
            'supplier_rut': final_df['supplier_vat'].astype(str),
            'avg_price': [format_avg_price(val) for val in final_df['avg_price']],
            'priority': final_df['priority'].astype(str)
        })

        self.logger.info(f"Final missing components dataframe shape (with suppliers): {result_df.shape}")
        if result_df.empty:
            self.logger.info("Note: This indicates that the missing components don't have supplier information in the current supplier database")
        else:
            print(result_df.head())

        return result_df

    def run_all_reports(self):
        """Run all reports and return dataframes"""
        # Clear cached data to ensure fresh results
        self.clear_cache()

        # Get supplier data from Odoo
        supplier_df = self.get_supplier_data()

        # Get missing products and components reports
        missing_products_df = self.get_missing_products_report()
        self.logger.info("-"*50)
        missing_components_df = self.get_missing_components_report()

        # Get final missing components dataframe
        final_missing_components_df = self.get_missing_components_final_df()

        # Return dataframes for potential further processing
        return {
            'supplier_data': supplier_df,
            'missing_products': missing_products_df,
            'missing_components': missing_components_df,
            'final_missing_components': final_missing_components_df
        }

    def clear_cache(self):
        """Clear all cached data"""
        self._supplier_data = None
        self._products_info = None
        self._missing_products = None
        self._missing_components = None

    def analyze_supplier_coverage(self):
        """Analyze which missing components have supplier information"""
        missing_components = self.get_missing_components()
        supplier_df = self.get_supplier_data()

        if missing_components.empty:
            self.logger.info("No missing components to analyze")
            return

        # Get unique product IDs from missing components
        missing_product_ids = set(missing_components['component_product_id'].unique())

        # Get unique product IDs from supplier data
        supplier_product_ids = set(supplier_df['product_id'].unique())

        # Find intersection
        common_products = missing_product_ids.intersection(supplier_product_ids)
        missing_without_supplier = missing_product_ids - supplier_product_ids

        self.logger.info(f"Missing components: {len(missing_product_ids)} unique products")
        self.logger.info(f"Supplier database: {len(supplier_product_ids)} unique products")
        self.logger.info(f"Missing components WITH supplier info: {len(common_products)}")
        self.logger.info(f"Missing components WITHOUT supplier info: {len(missing_without_supplier)}")

        return {
            'missing_with_supplier': common_products,
            'missing_without_supplier': missing_without_supplier,
            'supplier_coverage': len(common_products) / len(missing_product_ids) if missing_product_ids else 0
        }

def main():
    """Main function for standalone execution"""
    manager = SaleOrderManager()
    return manager.run_all_reports()
