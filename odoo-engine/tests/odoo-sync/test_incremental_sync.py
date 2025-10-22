import pytest
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from odoo_engine.sync_manager.models import Base, Product, SyncState
from odoo_engine.sync_manager.sync_manager import SyncManager
import datetime

@pytest.fixture
def in_memory_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    return Session()

def make_client_returning_products(records):
    client = MagicMock()
    def search_read(model, domain=None, fields=None, limit=None, offset=0, order=None):
        # simple slicing behavior
        start = offset or 0
        end = start + (limit or len(records))
        return records[start:end]
    client.search_read = MagicMock(side_effect=search_read)
    client.odoo = MagicMock()
    return client


def test_incremental_sync_initial_load(in_memory_session):
    client = make_client_returning_products([
        {"id": 10, "default_code": "SKU1", "name": "Prod1", "write_date": "2025-01-01 00:00:00"},
        {"id": 11, "default_code": "SKU2", "name": "Prod2", "write_date": "2025-01-02 00:00:00"},
    ])
    sync = SyncManager(in_memory_session, client)
    sync.sync_products()
    prods = in_memory_session.query(Product).all()
    assert len(prods) == 2
    state = in_memory_session.query(SyncState).filter_by(model_name="product.product").one_or_none()
    assert state is not None


def test_incremental_sync_subsequent_load(in_memory_session):
    in_memory_session.add(SyncState(model_name="product.product", last_synced=datetime.datetime(2025,1,2)))
    in_memory_session.commit()

    client = make_client_returning_products([
        {"id": 12, "default_code": "SKU3", "name": "Prod3", "write_date": "2025-01-03 00:00:00"},
    ])
    sync = SyncManager(in_memory_session, client)
    sync.sync_products()
    client.search_read.assert_called()
    prods = in_memory_session.query(Product).filter_by(odoo_id=12).all()
    assert len(prods) == 1
