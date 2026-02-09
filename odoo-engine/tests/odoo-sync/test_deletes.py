import datetime

import pytest
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from odoo_engine.sync_manager.models import Base, Product, SyncState
from odoo_engine.sync_manager.sync_manager import SyncManager

@pytest.fixture
def in_memory_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    return Session()


def make_client_returning_products(records):
    client = MagicMock()
    client.search_read = MagicMock(return_value=records)
    client.get_product_variant_attributes = MagicMock(return_value={})
    client.odoo = MagicMock()
    return client


def test_delete_detection_mark_inactive(in_memory_session):
    p1 = Product(odoo_id=1, default_code="A", name="A", active=True)
    p2 = Product(odoo_id=2, default_code="B", name="B", active=True)
    in_memory_session.add_all([p1, p2])
    in_memory_session.commit()

    client = make_client_returning_products([{"id":1, "default_code":"A", "name":"A", "write_date":"2025-01-01"}])
    sync = SyncManager(in_memory_session, client)
    sync.sync_products(delete_policy="mark_inactive")

    p2_refreshed = in_memory_session.query(Product).filter_by(odoo_id=2).one_or_none()
    assert p2_refreshed is not None
    assert p2_refreshed.active is False


def test_delete_detection_hard_delete(in_memory_session):
    p1 = Product(odoo_id=1, default_code="A", name="A", active=True)
    p2 = Product(odoo_id=2, default_code="B", name="B", active=True)
    in_memory_session.add_all([p1, p2])
    in_memory_session.commit()

    client = make_client_returning_products([{"id":1, "default_code":"A", "name":"A", "write_date":"2025-01-01"}])
    sync = SyncManager(in_memory_session, client)
    sync.sync_products(delete_policy="delete")

    p2_refreshed = in_memory_session.query(Product).filter_by(odoo_id=2).one_or_none()
    assert p2_refreshed is None


def test_incremental_sync_does_not_mark_inactive(in_memory_session):
    """When sync is incremental (last_synced exists), delete detection must be skipped."""
    # Pre-populate: 5 products exist in DB, all active
    for i in range(1, 6):
        in_memory_session.add(Product(odoo_id=i, name=f"Product {i}", active=True))
    in_memory_session.commit()

    # Set a previous sync timestamp to simulate incremental mode
    in_memory_session.add(SyncState(model_name="product.product", last_synced=datetime.datetime(2025, 1, 1)))
    in_memory_session.commit()

    # Odoo returns only product 3 (the only one modified since last sync)
    client = make_client_returning_products([
        {"id": 3, "default_code": "C", "name": "Product 3 updated", "write_date": "2025-06-01"},
    ])
    sync = SyncManager(in_memory_session, client)
    sync.sync_products(delete_policy="mark_inactive")

    # All 5 products must still be active (products 1,2,4,5 were NOT deleted in Odoo)
    all_products = in_memory_session.query(Product).order_by(Product.odoo_id).all()
    assert len(all_products) == 5
    for p in all_products:
        assert p.active is True, f"Product {p.odoo_id} was incorrectly marked inactive"
