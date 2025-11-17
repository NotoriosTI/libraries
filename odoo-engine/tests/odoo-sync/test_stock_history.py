import datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odoo_engine.sync_manager.models import (
    Base,
    Product,
    InventoryQuant,
    DailyStockHistory,
)
from odoo_engine.sync_manager.sync_manager import SyncManager


@pytest.fixture
def in_memory_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    return Session()


def _create_product(session, odoo_id=1, sku="SKU1", name="Prod1"):
    product = Product(
        odoo_id=odoo_id,
        default_code=sku,
        name=name,
    )
    session.add(product)
    session.commit()
    return product


def test_record_daily_stock_history_overwrites_per_location(in_memory_session):
    product = _create_product(in_memory_session)
    in_memory_session.add_all(
        [
            InventoryQuant(
                odoo_id=100,
                product_id=product.id,
                location_id=11,
                quantity=5,
            ),
            InventoryQuant(
                odoo_id=101,
                product_id=product.id,
                location_id=22,
                quantity=7,
            ),
        ]
    )
    in_memory_session.commit()

    sync = SyncManager(in_memory_session, MagicMock())
    snapshot_date = datetime.date(2024, 1, 10)
    sync.record_daily_stock_history(snapshot_date=snapshot_date)

    rows = (
        in_memory_session.query(DailyStockHistory)
        .filter_by(product_id=product.id, snapshot_date=snapshot_date)
        .order_by(DailyStockHistory.location_id)
        .all()
    )
    assert len(rows) == 2
    assert rows[0].location_id == 11
    assert rows[1].location_id == 22
    assert float(rows[0].quantity) == pytest.approx(5)
    assert float(rows[1].quantity) == pytest.approx(7)

    # Update quantities and ensure the snapshot overwrites for the day
    quant = in_memory_session.query(InventoryQuant).filter_by(odoo_id=101).one()
    quant.quantity = 3
    in_memory_session.add(quant)
    in_memory_session.commit()

    sync.record_daily_stock_history(snapshot_date=snapshot_date)

    rows = (
        in_memory_session.query(DailyStockHistory)
        .filter_by(product_id=product.id, snapshot_date=snapshot_date)
        .order_by(DailyStockHistory.location_id)
        .all()
    )
    assert len(rows) == 2
    assert rows[0].location_id == 11
    assert rows[1].location_id == 22
    assert float(rows[0].quantity) == pytest.approx(5)
    assert float(rows[1].quantity) == pytest.approx(3)
