import sys
sys.path.append('/home/snparada/Spacionatural/Libraries')
from sheets_lib.main_sheets import GoogleSheets
from odoo_lib.product import OdooProduct

# Uso de la clase para extraer el inventario
gs_sheet = GoogleSheets('1jtSgEmfkY7NbcQfklN_1ihveCwuQuW4-l4WShLcq-as')
odoo_product = OdooProduct()
all_products = odoo_product.read_all_products_in_dataframe()

gs_sheet.update_all_data_by_dataframe(all_products, 'Consolidado')

all_products.to_csv('/home/snparada/Spacionatural/Data/Dim/Odoo/all_products.csv', index=False)