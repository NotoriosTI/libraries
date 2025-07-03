import sys
sys.path.append('/home/snparada/Spacionatural/Libraries')
import pandas as pd
from odoo_lib.product import OdooProduct

odoo_product = OdooProduct()

tags_df = odoo_product.read_all_product_tags()

tags_df.to_csv('/home/snparada/Spacionatural/Data/Dim/Odoo/all_tag_products.csv', index=False)