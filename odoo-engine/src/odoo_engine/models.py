from sqlalchemy import (
    Column,
    BigInteger,
    Integer,
    String,
    Boolean,
    DateTime,
    Numeric,
    Text,
    JSON,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


# -------------------- Master Data --------------------
class UnitOfMeasure(Base):
    __tablename__ = "uom"
    id = Column(BigInteger, primary_key=True)
    odoo_id = Column(BigInteger, nullable=False, unique=True)
    name = Column(Text, nullable=False)
    category_id = Column(BigInteger)
    active = Column(Boolean)
    raw_json = Column(JSON)
    write_date = Column(DateTime(timezone=True))

    products = relationship("Product", back_populates="uom")
    boms = relationship("Bom", back_populates="uom")
    sale_order_lines = relationship("SaleOrderLine", back_populates="product_uom")
    purchase_order_lines = relationship(
        "PurchaseOrderLine", back_populates="product_uom"
    )

    __table_args__ = (
        Index("idx_uom_odoo_id", "odoo_id"),
        Index("idx_uom_name", "name"),
        Index("idx_uom_write_date", "write_date"),
    )


class Product(Base):
    __tablename__ = "product"
    id = Column(BigInteger, primary_key=True)
    odoo_id = Column(BigInteger, nullable=False, unique=True)
    default_code = Column(Text)
    name = Column(Text, nullable=False)
    sale_ok = Column(Boolean)
    purchase_ok = Column(Boolean)
    active = Column(Boolean)
    uom_id = Column(BigInteger, ForeignKey("uom.id"))
    type = Column(Text)
    barcode = Column(Text)
    raw_json = Column(JSON)
    write_date = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    uom = relationship("UnitOfMeasure", back_populates="products")
    boms = relationship("Bom", back_populates="product")
    bom_lines = relationship("BomLine", back_populates="component_product")
    sale_order_lines = relationship("SaleOrderLine", back_populates="product")
    purchase_order_lines = relationship("PurchaseOrderLine", back_populates="product")

    __table_args__ = (
        Index("idx_product_odoo_id", "odoo_id"),
        Index("idx_product_default_code", "default_code"),
        Index("idx_product_created_at", "created_at"),
        Index("idx_product_updated_at", "updated_at"),
        Index("idx_product_write_date", "write_date"),
    )


class Partner(Base):
    __tablename__ = "partner"
    id = Column(BigInteger, primary_key=True)
    odoo_id = Column(BigInteger, nullable=False, unique=True)
    name = Column(Text)
    is_company = Column(Boolean)
    supplier_rank = Column(Integer)
    customer_rank = Column(Integer)
    email = Column(Text)
    phone = Column(Text)
    raw_json = Column(JSON)
    write_date = Column(DateTime(timezone=True))

    sale_orders = relationship("SaleOrder", back_populates="partner")
    purchase_orders = relationship("PurchaseOrder", back_populates="partner")

    __table_args__ = (
        Index("idx_partner_odoo_id", "odoo_id"),
        Index("idx_partner_write_date", "write_date"),
    )


# -------------------- BOM / Production --------------------
class Bom(Base):
    __tablename__ = "bom"
    id = Column(BigInteger, primary_key=True)
    odoo_id = Column(BigInteger, nullable=False, unique=True)
    product_id = Column(BigInteger, ForeignKey("product.id"))
    company_id = Column(BigInteger)
    product_qty = Column(Numeric)
    uom_id = Column(BigInteger, ForeignKey("uom.id"))
    type = Column(Text)
    active = Column(Boolean)
    product_tmpl_id = Column(BigInteger)
    raw_json = Column(JSON)
    write_date = Column(DateTime(timezone=True))

    product = relationship("Product", back_populates="boms")
    uom = relationship("UnitOfMeasure", back_populates="boms")
    lines = relationship("BomLine", back_populates="bom")

    __table_args__ = (
        Index("idx_bom_odoo_id", "odoo_id"),
        Index("idx_bom_product_id", "product_id"),
        Index("idx_bom_write_date", "write_date"),
    )


class BomLine(Base):
    __tablename__ = "bom_line"
    id = Column(BigInteger, primary_key=True)
    odoo_id = Column(BigInteger, nullable=False, unique=True)
    bom_id = Column(BigInteger, ForeignKey("bom.id"))
    component_product_id = Column(BigInteger, ForeignKey("product.id"))
    product_qty = Column(Numeric)
    sequence = Column(Integer)
    operation_id = Column(BigInteger)
    raw_json = Column(JSON)
    write_date = Column(DateTime(timezone=True))

    bom = relationship("Bom", back_populates="lines")
    component_product = relationship("Product", back_populates="bom_lines")

    __table_args__ = (
        Index("idx_bom_line_odoo_id", "odoo_id"),
        Index("idx_bom_line_bom_id", "bom_id"),
        Index("idx_bom_line_component_product_id", "component_product_id"),
        Index("idx_bom_line_write_date", "write_date"),
    )


class ProductionOrder(Base):
    __tablename__ = "production_order"
    id = Column(BigInteger, primary_key=True)
    odoo_id = Column(BigInteger, nullable=False, unique=True)
    product_id = Column(BigInteger, ForeignKey("product.id"))
    product_qty = Column(Numeric)
    state = Column(String)
    company_id = Column(BigInteger)
    origin = Column(String)
    date_planned_start = Column(DateTime(timezone=True))
    date_planned_finished = Column(DateTime(timezone=True))
    raw_json = Column(JSON)
    write_date = Column(DateTime(timezone=True))

    product = relationship("Product")

    __table_args__ = (
        Index("idx_production_order_odoo_id", "odoo_id"),
        Index("idx_production_order_product_id", "product_id"),
        Index("idx_production_order_date_planned_start", "date_planned_start"),
        Index("idx_production_order_date_planned_finished", "date_planned_finished"),
        Index("idx_production_order_write_date", "write_date"),
    )


# -------------------- Inventory --------------------
class InventoryQuant(Base):
    __tablename__ = "inventory_quant"
    id = Column(BigInteger, primary_key=True)
    odoo_id = Column(BigInteger, nullable=False, unique=True)
    product_id = Column(BigInteger, ForeignKey("product.id"))
    location_id = Column(BigInteger)
    quantity = Column(Numeric)
    reserved_quantity = Column(Numeric)
    lot_id = Column(BigInteger)
    owner_id = Column(BigInteger)
    company_id = Column(BigInteger)
    raw_json = Column(JSON)
    write_date = Column(DateTime(timezone=True))

    product = relationship("Product")

    __table_args__ = (
        Index("idx_inventory_odoo_id", "odoo_id"),
        Index("idx_inventory_product_id", "product_id"),
        Index("idx_inventory_write_date", "write_date"),
    )


# -------------------- Sales --------------------
class SaleOrder(Base):
    __tablename__ = "sale_order"
    id = Column(BigInteger, primary_key=True)
    odoo_id = Column(BigInteger, nullable=False, unique=True)
    partner_id = Column(BigInteger, ForeignKey("partner.id"))
    date_order = Column(DateTime(timezone=True))
    state = Column(String)
    amount_total = Column(Numeric)
    raw_json = Column(JSON)
    write_date = Column(DateTime(timezone=True))

    partner = relationship("Partner", back_populates="sale_orders")
    lines = relationship("SaleOrderLine", back_populates="order")

    __table_args__ = (
        Index("idx_sale_order_odoo_id", "odoo_id"),
        Index("idx_sale_order_partner_id", "partner_id"),
        Index("idx_sale_order_date_order", "date_order"),
        Index("idx_sale_order_write_date", "write_date"),
    )


class SaleOrderLine(Base):
    __tablename__ = "sale_order_line"
    id = Column(BigInteger, primary_key=True)
    odoo_id = Column(BigInteger, nullable=False, unique=True)
    order_id = Column(BigInteger, ForeignKey("sale_order.id"))
    product_id = Column(BigInteger, ForeignKey("product.id"))
    product_uom_id = Column(BigInteger, ForeignKey("uom.id"))
    quantity = Column(Numeric)
    unit_price = Column(Numeric)
    raw_json = Column(JSON)
    write_date = Column(DateTime(timezone=True))

    order = relationship("SaleOrder", back_populates="lines")
    product = relationship("Product", back_populates="sale_order_lines")
    product_uom = relationship("UnitOfMeasure", back_populates="sale_order_lines")

    __table_args__ = (
        Index("idx_sale_order_line_odoo_id", "odoo_id"),
        Index("idx_sale_order_line_order_id", "order_id"),
        Index("idx_sale_order_line_product_id", "product_id"),
        Index("idx_sale_order_line_write_date", "write_date"),
    )


# -------------------- Purchase --------------------
class PurchaseOrder(Base):
    __tablename__ = "purchase_order"
    id = Column(BigInteger, primary_key=True)
    odoo_id = Column(BigInteger, nullable=False, unique=True)
    partner_id = Column(BigInteger, ForeignKey("partner.id"))
    date_order = Column(DateTime(timezone=True))
    state = Column(String)
    amount_total = Column(Numeric)
    raw_json = Column(JSON)
    write_date = Column(DateTime(timezone=True))

    partner = relationship("Partner", back_populates="purchase_orders")
    lines = relationship("PurchaseOrderLine", back_populates="order")

    __table_args__ = (
        Index("idx_purchase_order_odoo_id", "odoo_id"),
        Index("idx_purchase_order_partner_id", "partner_id"),
        Index("idx_purchase_order_date_order", "date_order"),
        Index("idx_purchase_order_write_date", "write_date"),
    )


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_line"
    id = Column(BigInteger, primary_key=True)
    odoo_id = Column(BigInteger, nullable=False, unique=True)
    order_id = Column(BigInteger, ForeignKey("purchase_order.id"))
    product_id = Column(BigInteger, ForeignKey("product.id"))
    product_uom_id = Column(BigInteger, ForeignKey("uom.id"))
    quantity = Column(Numeric)
    unit_price = Column(Numeric)
    raw_json = Column(JSON)
    write_date = Column(DateTime(timezone=True))

    order = relationship("PurchaseOrder", back_populates="lines")
    product = relationship("Product", back_populates="purchase_order_lines")
    product_uom = relationship("UnitOfMeasure", back_populates="purchase_order_lines")

    __table_args__ = (
        Index("idx_purchase_order_line_odoo_id", "odoo_id"),
        Index("idx_purchase_order_line_order_id", "order_id"),
        Index("idx_purchase_order_line_product_id", "product_id"),
        Index("idx_purchase_order_line_write_date", "write_date"),
    )


# -------------------- Sync State --------------------
class SyncState(Base):
    __tablename__ = "sync_state"
    model_name = Column(String, primary_key=True)
    last_synced = Column(DateTime(timezone=True), index=True)
