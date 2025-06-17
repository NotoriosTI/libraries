from odoo_api import OdooProduct

product_api = OdooProduct('test', '/Users/bastianibanez/work/libraries/odoo-api/.env')
last_mo = product_api.get_last_mo_draft()
print(last_mo)