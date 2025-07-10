from src.odoo_api.product import OdooProduct
from config_manager import secrets

odoo_product = OdooProduct(
    db=secrets.ODOO_TEST_DB,
    url=secrets.ODOO_TEST_URL,
    username=secrets.ODOO_TEST_USERNAME,
    password=secrets.ODOO_TEST_PASSWORD,
    )

def test_read_products_names():
    """
    Test para verificar que los nombres extraídos de Odoo sean correctos usando read_products_for_embeddings.
    """
    from odoo_api.product import OdooProduct
    import pandas as pd

    # Instancia real o mockeada según el entorno
    # Aquí se asume que hay una configuración de test o un entorno de prueba

    # Extraer productos (puedes limitar el dominio para acelerar el test)
    print("Reading products for embeddings")
    df = odoo_product.read_products_for_embeddings(domain=[])

    # Verificar que el DataFrame no esté vacío
    assert not df.empty, "No se extrajeron productos de Odoo."

    # Verificar que la columna 'name' existe
    assert 'name' in df.columns, "No se extrajo la columna 'name' (nombre de producto/variante)."

    # Imprimir los primeros nombres extraídos para inspección manual
    print("Primeros nombres extraídos:", df['name'].head(10).tolist())

    # Ejemplo de aserción: puedes ajustar según tus datos de test
    for name in df['name'].head(10):
        assert isinstance(name, str) and len(name) > 0, f"Nombre inválido extraído: {name}"

def test_read_coconut_oil_variants():
    """
    Test para extraer y verificar variantes de aceite de coco desde Odoo.
    """
    # Dominio Odoo: productos activos cuyo nombre contiene 'coco'
    domain = [
        ['active', '=', True],
        ['name', 'ilike', 'fraccionado']
    ]
    print("Extrayendo variantes de aceite de coco...")
    df = odoo_product.read_products_for_embeddings(domain=domain)

    assert not df.empty, "No se encontraron variantes de aceite de coco."
    print("Nombres de variantes de aceite de coco extraídas:")
    print(df['name'].tolist())

    # Todos los nombres deben contener 'coco'
    for name in df['name']:
        assert 'coco' in name.lower(), f"Nombre inesperado: {name}"

def test_read_coconut_oil_variants_with_attributes():
    domain = [
        ['active', '=', True],
        ['name', 'ilike', 'fraccionado']
    ]
    print("Extrayendo variantes de aceite de coco (con atributos, batch)...")
    df = odoo_product.read_products_for_embeddings(domain=domain)

    assert not df.empty, "No se encontraron variantes de aceite de coco fraccionado."

    skus = df['default_code'].tolist()
    atributos_dict = odoo_product.get_variant_attributes_by_sku(skus)

    for idx, row in df.iterrows():
        name = row['name']
        sku = row['default_code']
        atributos = atributos_dict.get(sku, [])
        if atributos:
            if isinstance(atributos, list):
                atributos_str = ", ".join(atributos)
            else:
                atributos_str = str(atributos)
            nombre_completo = f"{name} ({atributos_str})"
        else:
            nombre_completo = name
        print(nombre_completo)


if __name__ == "__main__":
    # test_read_products_names()
    # test_read_coconut_oil_variants()
    test_read_coconut_oil_variants_with_attributes()