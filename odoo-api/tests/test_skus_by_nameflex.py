from odoo_api import OdooProduct

def test_skus_by_nameflex():
    product = OdooProduct(dotenv_path='.env')
    skus = product.get_skus_by_name_flexible('Aceite de coco')
    print(skus)
    
if __name__ == "__main__":
    test_skus_by_nameflex()