import pytest
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from odoo_engine.sync_manager.models import Base, Product
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
