from odoo_api import OdooProduct

product_api = OdooProduct('test', '/Users/bastianibanez/work/libraries/odoo-api/.env')

last_mo = product_api.get_last_mo_draft()
last_mo_id = last_mo['mo_id']
last_mo_name = last_mo['mo_name']
last_mo_product = last_mo['product_name']
last_mo_qty = last_mo['product_qty']

print(f"{last_mo_id = }")
print(f"{last_mo_name = }")
print(f"{last_mo_product = }")
print(f"{last_mo_qty = }")

if input("Confirm? [y/N]: ") == "y":
    product_api.confirm_mo(last_mo_id)