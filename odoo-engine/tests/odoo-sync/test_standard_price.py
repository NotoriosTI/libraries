import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odoo_engine.sync_manager.models import Base, Product


@pytest.fixture
def in_memory_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    return Session()


def test_product_has_standard_price_column(in_memory_session):
    product = Product(odoo_id=1, name="Aceite de coco", standard_price=1500.50)
    in_memory_session.add(product)
    in_memory_session.commit()

    stored = in_memory_session.query(Product).filter_by(odoo_id=1).one()
    assert float(stored.standard_price) == pytest.approx(1500.50)


def test_product_standard_price_nullable(in_memory_session):
    product = Product(odoo_id=2, name="Jabón natural")
    in_memory_session.add(product)
    in_memory_session.commit()

    stored = in_memory_session.query(Product).filter_by(odoo_id=2).one()
    assert stored.standard_price is None


def test_product_standard_price_false_becomes_none(in_memory_session):
    """Simulate Odoo returning False for an empty numeric field."""
    raw_value = False
    coerced = raw_value or None

    product = Product(odoo_id=3, name="Crema hidratante", standard_price=coerced)
    in_memory_session.add(product)
    in_memory_session.commit()

    stored = in_memory_session.query(Product).filter_by(odoo_id=3).one()
    assert stored.standard_price is None
