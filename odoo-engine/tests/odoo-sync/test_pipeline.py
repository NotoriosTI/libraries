import pytest
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from odoo_engine.sync_manager.models import Base, UnitOfMeasure, Product
from odoo_engine.sync_manager.sync_manager import SyncManager

@pytest.fixture
def in_memory_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    return Session()


def test_pipeline_ordering_and_mapping(in_memory_session):
    client = MagicMock()
    client.search_read = MagicMock(side_effect=[
        [{"id": 100, "name":"UOM1", "write_date":"2025-01-01"}],
        [{"id": 200, "default_code":"P1", "name":"Prod1", "uom_id":[100], "write_date":"2025-01-02"}]
    ])
    client.get_product_variant_attributes = MagicMock(return_value={200: ["100ml"]})
    sync = SyncManager(in_memory_session, client)
    sync.sync_uoms()
    sync.sync_products()
    uoms = in_memory_session.query(UnitOfMeasure).all()
    prods = in_memory_session.query(Product).all()
    assert len(uoms) == 1
    assert len(prods) == 1
    assert prods[0].uom_id is not None
    assert prods[0].name == "Prod1 (100ml)"
