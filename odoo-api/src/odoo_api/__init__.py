from .product import OdooProduct

__all__ = ['OdooProduct']




    



# def test(): 
    
#     odoo_api = product.OdooProduct(database='test', dotenv_path='.env')

#     name_or_sku = "aceite de coco"
    
#     if odoo_api.product_exists(name_or_sku):
#         # Direct order
#         pass

#     flexible_search = odoo_api.get_skus_by_name_flexible(name_or_sku)

#     if not flexible_search:
#         # Error
#         pass

#     if len(flexible_search) == 1:
#         # Direct order
#         pass

#     if len(flexible_search) > 1:
#         # Interrupt and select
#         pass


# if __name__ == "__main__":
#     test()

