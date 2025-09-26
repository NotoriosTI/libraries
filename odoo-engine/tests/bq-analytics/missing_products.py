import google.cloud.bigquery as bq
import pandas as pd

client = bq.Client()

missing_products_query = """
SELECT * FROM `notorios.sales_analytics.product_missing_current_month`
"""
missing_products_query_job = client.query_and_wait(missing_products_query)
missing_products_df = missing_products_query_job.to_dataframe()

missing_components_query = """
SELECT * FROM `notorios.sales_analytics.required_component_orders_current_month`
"""
missing_components_query_job = client.query_and_wait(missing_components_query)
missing_components_df = missing_components_query_job.to_dataframe()

print(missing_products_df.info())
print(missing_products_df.head())
print(missing_components_df.info())
print(missing_components_df.head())