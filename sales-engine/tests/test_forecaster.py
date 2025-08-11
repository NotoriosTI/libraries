from sales_engine.forecaster.production_forecast_updater import get_inventory_from_odoo
print(get_inventory_from_odoo(['6429','8095']))  # strings
print(get_inventory_from_odoo([6429,8095]))      # ints