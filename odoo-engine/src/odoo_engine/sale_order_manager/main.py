from odoo_engine.utils import get_pg_dsn
from sqlalchemy import create_engine, text

PRODUCT_DEFAULT_CODES = [
    "MP100",
    "MP014",
    "MP029"
]

default_codes_str = "("
for i, code in enumerate(PRODUCT_DEFAULT_CODES):
    if i == len(PRODUCT_DEFAULT_CODES) - 1:
        default_codes_str += f"'{code}'"
        break
    default_codes_str += f"'{code}', "
default_codes_str += ")"

supplier_data_query = """
WITH price_data AS (
    SELECT 
        p.odoo_id AS product_id,
        p.default_code AS product_default_code,
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
    WHERE p.default_code IN {}
      AND prt.supplier_rank > 0
)
SELECT 
    product_id,
    product_default_code,
    supplier_name,
    supplier_vat,
    MIN(unit_price) AS min_price,
    MAX(unit_price) AS max_price,
    AVG(unit_price) AS avg_price,
    MAX(CASE WHEN rn = 1 THEN unit_price END) AS last_price
FROM price_data
GROUP BY product_id, product_default_code, supplier_name, supplier_vat
ORDER BY product_default_code, supplier_name;
"""

def main():
    dsn = get_pg_dsn()
    engine = create_engine(dsn, echo=False, future=True)
    with engine.connect() as conn:
        result = conn.execute(text(supplier_data_query.format(default_codes_str)))
        for row in result:
            print(row)

if __name__ == "__main__":
    main()