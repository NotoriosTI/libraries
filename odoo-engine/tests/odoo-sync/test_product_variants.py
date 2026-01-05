import pytest
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odoo_engine.sync_manager.models import Base, Product
from odoo_engine.sync_manager.sync_manager import SyncManager
from odoo_engine.utils.odoo_client import OdooClient
import os


@pytest.fixture
def in_memory_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    return Session()


def test_get_product_variant_attributes_resolves_names_and_preserves_order():
    # Evitamos __init__ (conexión real) creando la instancia sin inicializar.
    client = OdooClient.__new__(OdooClient)

    # Simulamos la lectura en Odoo:
    # - product.product devuelve ids de atributos (con duplicados)
    # - product.template.attribute.value devuelve id->name
    def fake_read(model, ids, fields=None):
        if model == "product.product":
            assert set(fields or []) == {"id", "product_template_attribute_value_ids"}
            return [
                {"id": 1, "product_template_attribute_value_ids": [10, 11, 10]},
                {"id": 2, "product_template_attribute_value_ids": []},
            ]
        if model == "product.template.attribute.value":
            assert set(fields or []) == {"id", "name"}
            # el método debe deduplicar ids antes de llamar; igual devolvemos ambos
            return [
                {"id": 10, "name": "100ml"},
                {"id": 11, "name": "1L"},
            ]
        raise AssertionError(f"Modelo inesperado: {model}")

    client.read = MagicMock(side_effect=fake_read)

    attrs = client.get_product_variant_attributes([1, 2, 999])

    print("\n[debug] attributes_by_product_id:")
    for pid in sorted(attrs.keys()):
        print(f"  product_id={pid}: {attrs[pid]}")

    # - Producto 1: dedupe y orden: 10,11
    assert attrs[1] == ["100ml", "1L"]
    # - Producto 2: sin atributos
    assert attrs[2] == []
    # - IDs pedidos siempre presentes en respuesta
    assert attrs[999] == []


def test_sync_products_combines_name_with_variant_attributes(in_memory_session):
    client = MagicMock()

    # search_read es usado por _fetch_in_batches; simulamos una sola página.
    client.search_read = MagicMock(
        return_value=[
            {"id": 1, "default_code": "1000001", "name": "Aceite de coco", "uom_id": None, "write_date": "2025-01-01"},
            {"id": 2, "default_code": "1000002", "name": "Aceite de coco", "uom_id": None, "write_date": "2025-01-01"},
            {"id": 3, "default_code": "1000003", "name": "Aceite de coco", "uom_id": None, "write_date": "2025-01-01"},
        ]
    )

    client.get_product_variant_attributes = MagicMock(
        return_value={
            1: ["100ml"],
            2: ["1L"],
            3: ["500ml", "Orgánico"],
        }
    )

    sync = SyncManager(in_memory_session, client)
    sync.sync_products()

    p1 = in_memory_session.query(Product).filter_by(odoo_id=1).one()
    p2 = in_memory_session.query(Product).filter_by(odoo_id=2).one()
    p3 = in_memory_session.query(Product).filter_by(odoo_id=3).one()

    print("\n[debug] synced products:")
    for p in (p1, p2, p3):
        print(f"  odoo_id={p.odoo_id} default_code={p.default_code} name={p.name}")

    assert p1.name == "Aceite de coco (100ml)"
    assert p2.name == "Aceite de coco (1L)"
    assert p3.name == "Aceite de coco (500ml, Orgánico)"


@pytest.mark.integration
def test_integration_print_coconut_oil_variants_from_real_odoo():
    """Imprime variantes reales desde Odoo.

    Por defecto se salta para no depender de red/credenciales en CI.
    Ejecutar local con:
        RUN_ODOO_INTEGRATION=1 poetry run pytest -vs -s tests/odoo-sync/test_product_variants.py -k integration
    """
    if os.getenv("RUN_ODOO_INTEGRATION") != "1":
        pytest.skip("Set RUN_ODOO_INTEGRATION=1 to run this test")

    client = OdooClient()

    # Buscar productos cuyo nombre contenga 'Aceite de coco'
    domain = [["name", "ilike", "Aceite de coco"], ["detailed_type", "!=", "service"]]
    records = client.search_read(
        "product.product",
        domain=domain,
        fields=["id", "default_code", "name"],
        limit=200,
        offset=0,
    )

    product_ids = [r.get("id") for r in records if r.get("id")]
    attrs_by_id = client.get_product_variant_attributes(product_ids)

    print("\n[integration] Aceite de coco variants (odoo_id, default_code, name):")
    shown = 0
    for r in records:
        pid = r.get("id")
        base_name = r.get("name") or ""
        attrs = attrs_by_id.get(pid, []) or []
        full_name = f"{base_name} ({', '.join(attrs)})" if (base_name and attrs) else base_name
        print(f"  odoo_id={pid} default_code={r.get('default_code')} name={full_name}")
        shown += 1

    assert shown > 0
