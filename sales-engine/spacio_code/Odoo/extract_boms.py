import sys
sys.path.append('/home/snparada/Spacionatural/Libraries')
import pandas as pd
from odoo_lib.product import OdooProduct

"""
1. Load Raw Data and pre-formatting
"""

odoo_product = OdooProduct()
df_product_bom = odoo_product.read_all_bills_of_materials_in_dataframe()
# df_product_bom = pd.read_csv('/home/snparada/Spacionatural/Data/Dim/Odoo/all_boms.csv')
df_products = pd.read_csv('/home/snparada/Spacionatural/Data/Dim/Odoo/all_products.csv', usecols={'id', 'all_product_tag_ids', 'default_code', 'code'})
df_all_tags = pd.read_csv('/home/snparada/Spacionatural/Data/Dim/Odoo/all_tag_products.csv')


df_products['sku'] = df_products['default_code'].fillna(df_products['code'])
df_products.drop(columns=['default_code', 'code'], inplace=True)
df_products['id'] = df_products['id'].astype(str)
df_products['all_product_tag_ids'] = df_products['all_product_tag_ids'].apply(lambda x: str(x).strip('[]').split(',')[0] if pd.notna(x) else '')
df_products['all_product_tag_ids'] = df_products['all_product_tag_ids'].astype(str)
df_all_tags['id'] = df_all_tags['id'].astype(str)
df_product_bom['manufactured_product_id'] = df_product_bom['manufactured_product_id'].astype(str)
df_product_bom['component_product_id'] = df_product_bom['component_product_id'].astype(str)


"""
2. Transforming the data
"""


# Merge df_product_bom with df_products to get the 'sku' and 'tags' for 'manufactured_product_id'
df_product_bom = df_product_bom.merge(df_products[['id', 'sku']], left_on='manufactured_product_id', right_on='id', how='left')
df_product_bom.rename(columns={'sku': 'manufactured_product_sku'}, inplace=True)

# Merge df_product_bom with df_products again to get the 'sku' for 'component_product_id'
df_product_bom = df_product_bom.merge(df_products[['id', 'sku', 'all_product_tag_ids']], left_on='component_product_id', right_on='id', how='left')
df_product_bom.rename(columns={'sku': 'component_product_sku'}, inplace=True)

df_product_bom = df_product_bom.merge(df_all_tags[['id', 'name']], left_on='all_product_tag_ids', right_on='id', how='left')



# Clean up columns
df_product_bom = df_product_bom.drop(columns=['id_x', 'id_y'])


"""
3. Saving the data
"""

df_product_bom.to_csv('/home/snparada/Spacionatural/Data/Dim/Odoo/all_boms.csv', index=False)

