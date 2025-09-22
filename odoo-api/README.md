# Odoo API Client
A Python library designed to streamline interaction with the Odoo ERP API. It provides a set of high-level classes and methods for managing common Odoo models such as Products, Sales, CRM, Customers, and more. Built on top of Odoo's XML-RPC API, this library simplifies data operations and is ideal for automation scripts, data synchronization tasks, and integration with other systems, including AI agents.

-----

## Features

  * **Object-Oriented Design**: High-level classes for different Odoo modules (`Product`, `CRM`, `Sales`, `Customer`, etc.).
  * **Simplified Connection**: Handles authentication and connection to multiple Odoo databases (production and test) seamlessly.
  * **Environment-Based Configuration**: Securely manages Odoo credentials using a `.env` file.
  * **Comprehensive Functionality**: Covers a wide range of operations:
      * **Product Management**: CRUD for products, inventory updates, BOM management, and production order creation.
      * **CRM**: Manage opportunities, quotations, and stages.
      * **Sales**: Read sales orders from both standard Sales and Point of Sale (POS) modules.
      * **Customer Management**: Create, read, and find customers by various attributes.
      * **Inventory & Warehousing**: Perform inventory adjustments and read stock levels by location.
      * **Accounting**: Handle journal entries, account balances, and reconciliation.
  * **Pandas Integration**: Many methods return data as pandas DataFrames for easy analysis and manipulation.

## Installation

Using Poetry locally:

```bash
cd odoo-api
poetry install
```

As a dependency from the monorepo:

```bash
pip install -e odoo-api/
```

## Configuration

You can construct clients directly by passing credentials, or use `config-manager` to centralize environment configuration. Example using explicit credentials:

```python
from odoo_api.product import OdooProduct

client = OdooProduct(
  db="your_db",
  url="https://your-odoo",
  username="user",
  password="pass",
)
```

When used together with `config-manager`, read secrets from environment/Secret Manager and pass them to the constructor.

## Quick Start

Here’s a simple example of how to instantiate a class and retrieve data from Odoo.

First, ensure your `.env` file is set up. Then, you can use any of the library's classes. For example, to read a customer by their email:

```python
from odoo_api.customers import OdooCustomers

# Instantiate the client for the 'productive' database
customer_manager = OdooCustomers(database='productive')

# Read a customer by their email address
customer_df = customer_manager.read_customer_by_email('customer-email@example.com')

if isinstance(customer_df, pd.DataFrame) and not customer_df.empty:
    print("Customer found:")
    print(customer_df)
else:
    print(customer_df) # Will print "Customer not found" or an error message

```

-----

## API Reference

The library is organized into several classes, each mapping to an Odoo module.

  * `OdooAPI`: The base class that handles the connection and authentication.
  * `OdooProduct`: Manages products, variants, bills of materials, and production orders.
  * `OdooCRM`: Handles CRM opportunities, quotations, and stages.
  * `OdooCustomers`: Manages customer contacts (res.partner).
  * `OdooSales`: Reads sales orders from the main sales and PoS modules.
  * `OdooWarehouse`: Manages stock levels and inventory adjustments.
  * `OdooJournal` & `OdooAccountability`: Handle accounting journals and accounts.

### OdooProduct Class Reference

This class provides a comprehensive interface for interacting with product-related models in Odoo. It inherits from the base `OdooAPI` class.

**Initialization**

```python
from odoo_api.product import OdooProduct

# To connect to the test database
product_manager = OdooProduct(database='test')

# To connect to the production database
product_manager = OdooProduct(database='productive')
```

\<br\>

-----

#### **create\_product**

Creates a new product in Odoo. It first checks if a product with the same SKU (`default_code`) already exists to prevent duplicates.

  * **Signature**: `create_product(self, product_data: dict) -> str`
  * **Parameters**:
      * `product_data` (dict): A dictionary containing the product fields. Key fields include `name`, `default_code`, `list_price`, etc.
  * **Returns**: `str` - A confirmation message indicating the result of the operation.
  * **Example**:
    ```python
    response = product_manager.create_product({
        'default_code': 'SKU12345',
        'name': 'New Awesome Product',
        'list_price': 99.99,
        'sale_ok': True
    })
    print(response)
    ```

-----

#### **update\_product**

Updates an existing product in Odoo, identified by its SKU.

  * **Signature**: `update_product(self, sku: str, df: DataFrame) -> str` (Note: the original documentation refers to a DataFrame `df`, but the implementation uses a dictionary. The documentation here follows the implementation found in `update_product_from_data`).
  * **Parameters**:
      * `sku` (str): The SKU (`default_code`) of the product to update.
      * `product_data` (dict): A dictionary containing the fields to update.
  * **Returns**: `str` - A confirmation message.
  * **Example**:
    ```python
    response = product_manager.update_product_from_data('SKU12345', {
        'list_price': 109.99,
        'purchase_ok': True
    })
    print(response)
    ```

-----

#### **product\_exists**

Checks if a product with a given SKU exists in Odoo.

  * **Signature**: `product_exists(self, sku: str) -> bool`
  * **Parameters**:
      * `sku` (str): The SKU (`default_code`) to check.
  * **Returns**: `bool` - `True` if the product exists, `False` otherwise.
  * **Example**:
    ```python
    if product_manager.product_exists('SKU12345'):
        print("Product exists!")
    else:
        print("Product not found.")
    ```

-----

#### **get\_skus\_by\_name\_flexible**

Searches for products whose name contains a given partial text (case-insensitive).

  * **Signature**: `get_skus_by_name_flexible(self, partial_name: str) -> list[dict]`
  * **Parameters**:
      * `partial_name` (str): The partial name to search for.
  * **Returns**: `list[dict]` - A list of dictionaries, each containing the `id`, `default_code` (SKU), and `name` of a matching product.
  * **Example**:
    ```python
    products = product_manager.get_skus_by_name_flexible('Aceite de Coco')
    for p in products:
        print(f"ID: {p['id']}, SKU: {p['default_code']}, Name: {p['name']}")
    ```

-----

#### **read\_all\_products\_in\_dataframe**

Retrieves all products from Odoo and returns them as a pandas DataFrame. It fetches data in batches to handle large datasets efficiently.

  * **Signature**: `read_all_products_in_dataframe(self, batch_size: int = 100) -> pd.DataFrame`
  * **Parameters**:
      * `batch_size` (int, optional): The number of products to fetch per API call. Defaults to 100.
  * **Returns**: `pd.DataFrame` - A DataFrame containing all products, with image-related columns removed for efficiency.
  * **Example**:
    ```python
    all_products_df = product_manager.read_all_products_in_dataframe()
    print(f"Total products found: {len(all_products_df)}")
    print(all_products_df.head())
    ```

-----

#### **read\_all\_bills\_of\_materials\_in\_dataframe**

Reads all Bill of Materials (BOMs) and their components, returning a structured pandas DataFrame.

  * **Signature**: `read_all_bills_of_materials_in_dataframe(self) -> pd.DataFrame`
  * **Returns**: `pd.DataFrame` - A DataFrame with columns `manufactured_product_id`, `component_product_id`, and `quantity_needed`.
  * **Example**:
    ```python
    boms_df = product_manager.read_all_bills_of_materials_in_dataframe()
    print(boms_df.head())
    ```

-----

#### **create\_production\_orders**

Creates manufacturing orders based on data provided in a pandas DataFrame. It includes advanced logic to find the correct BOM for each product (checking for variant-specific BOMs before template-level BOMs).

  * **Signature**: `create_production_orders(self, df_production: pd.DataFrame) -> str`
  * **Parameters**:
      * `df_production` (pd.DataFrame): A DataFrame with columns for `SKU` and `TOTAL PRODUCCIÓN`.
  * **Returns**: `str` - A log of the creation process, detailing successes and failures for each row.
  * **Example**:
    ```python
    import pandas as pd
    data = {'SKU': ['PROD-A-01', 'PROD-B-02'], 'TOTAL PRODUCCIÓN': [50, 75]}
    production_plan_df = pd.DataFrame(data)
    result_log = product_manager.create_production_orders(production_plan_df)
    print(result_log)
    ```

-----

#### **get\_last\_mo\_draft**

Fetches the most recent manufacturing order (MO) that is still in the 'draft' state.

  * **Signature**: `get_last_mo_draft(self) -> dict`
  * **Returns**: `dict` - A dictionary containing the `mo_id`, `mo_name`, `product_name`, and `product_qty` of the latest draft MO.
  * **Example**:
    ```python
    last_mo = product_manager.get_last_mo_draft()
    if last_mo:
        print(f"Last draft MO is {last_mo['mo_name']} for {last_mo['product_qty']} units of {last_mo['product_name']}.")
    ```

-----

#### **confirm\_mo**

Confirms a draft manufacturing order, which typically triggers the next steps in the production process.

  * **Signature**: `confirm_mo(self, mo_id: int) -> bool`
  * **Parameters**:
      * `mo_id` (int): The ID of the manufacturing order to confirm.
  * **Returns**: `bool` - `True` if the confirmation was successful, `False` otherwise.
  * **Example**:
    ```python
    last_mo = product_manager.get_last_mo_draft()
    if last_mo:
        mo_id_to_confirm = last_mo['mo_id']
        success = product_manager.confirm_mo(mo_id_to_confirm)
        if success:
            print(f"MO {mo_id_to_confirm} has been confirmed.")
        else:
            print(f"Failed to confirm MO {mo_id_to_confirm}.")
    ```

-----

#### **Auxiliary Methods**

  * **`get_id_by_sku(sku)`**: Retrieves the internal Odoo database ID for a product given its SKU.
  * **`get_sku_by_id(product_id)`**: Retrieves the SKU of a product given its internal Odoo ID.
  * **`get_category_id_by_name(category_name)`**: Finds the database ID of a product category from its display name.
  * **`process_field_value(value, command_type)`**: A helper to correctly format data for updating many2many relationships in Odoo (e.g., product tags or routes). The `command_type` can be `add`, `replace`, or `remove`.