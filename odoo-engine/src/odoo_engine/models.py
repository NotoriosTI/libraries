from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Text,
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


# ------------------------
# Utility / Sync state
# ------------------------
class SyncState(Base):
    __tablename__ = "sync_state"

    id = Column(Integer, primary_key=True)
    model = Column(String, unique=True, nullable=False)
    last_sync = Column(DateTime)


# ------------------------
# Units of Measure
# ------------------------
class UoM(Base):
    __tablename__ = "uoms"

    id = Column(Integer, primary_key=True)
    odoo_id = Column(Integer, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    category = Column(String)

    products = relationship("Product", back_populates="uom")
    boms = relationship("BillOfMaterial", back_populates="uom")
    bom_lines = relationship("BillOfMaterialLine", back_populates="uom")


# ------------------------
# Partners (customers, suppliers)
# ------------------------
class Partner(Base):
    __tablename__ = "partners"

    id = Column(Integer, primary_key=True)
    odoo_id = Column(Integer, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    supplier_rank = Column(Integer, default=0)
    customer_rank = Column(Integer, default=0)

    sale_orders = relationship("SaleOrder", back_populates="partner")
    purchase_orders = relationship("PurchaseOrder", back_populates="partner")


# ------------------------
# Products
# ------------------------
class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    odoo_id = Column(Integer, unique=True, index=True, nullable=False)
    default_code = Column(String, index=True)  # SKU
    name = Column(String, nullable=False)
    type = Column(String)
    sale_ok = Column(Boolean, default=False)
    purchase_ok = Column(Boolean, default=False)
    uom_id = Column(Integer, ForeignKey("uoms.odoo_id"))

    uom = relationship("UoM", back_populates="products")

    bom_lines = relationship("BillOfMaterialLine", back_populates="product")
    production_orders = relationship("ProductionOrder", back_populates="product")
    inventory_quants = relationship("InventoryQuant", back_populates="product")
    sale_order_lines = relationship("SaleOrderLine", back_populates="product")
    purchase_order_lines = relationship("PurchaseOrderLine", back_populates="product")


# ------------------------
# Bill of Materials
# ------------------------
class BillOfMaterial(Base):
    __tablename__ = "boms"

    id = Column(Integer, primary_key=True)
    odoo_id = Column(Integer, unique=True, index=True, nullable=False)
    product_id = Column(Integer, ForeignKey("products.odoo_id"))
    quantity = Column(Float, default=0.0)
    uom_id = Column(Integer, ForeignKey("uoms.odoo_id"))

    uom = relationship("UoM", back_populates="boms")
    lines = relationship("BillOfMaterialLine", back_populates="bom")


class BillOfMaterialLine(Base):
    __tablename__ = "bom_lines"

    id = Column(Integer, primary_key=True)
    odoo_id = Column(Integer, unique=True, index=True, nullable=False)
    bom_id = Column(Integer, ForeignKey("boms.odoo_id"))
    product_id = Column(Integer, ForeignKey("products.odoo_id"))
    quantity = Column(Float, default=0.0)
    uom_id = Column(Integer, ForeignKey("uoms.odoo_id"))

    bom = relationship("BillOfMaterial", back_populates="lines")
    product = relationship("Product", back_populates="bom_lines")
    uom = relationship("UoM", back_populates="bom_lines")


# ------------------------
# Production Orders
# ------------------------
class ProductionOrder(Base):
    __tablename__ = "production_orders"

    id = Column(Integer, primary_key=True)
    odoo_id = Column(Integer, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    product_id = Column(Integer, ForeignKey("products.odoo_id"))
    quantity = Column(Float, default=0.0)
    date_planned_start = Column(DateTime)
    date_finished = Column(DateTime)

    product = relationship("Product", back_populates="production_orders")


# ------------------------
# Inventory Quants
# ------------------------
class InventoryQuant(Base):
    __tablename__ = "inventory_quants"

    id = Column(Integer, primary_key=True)
    odoo_id = Column(Integer, unique=True, index=True, nullable=False)
    product_id = Column(Integer, ForeignKey("products.odoo_id"))
    location = Column(String)
    quantity = Column(Float, default=0.0)

    product = relationship("Product", back_populates="inventory_quants")


# ------------------------
# Sales Orders
# ------------------------
class SaleOrder(Base):
    __tablename__ = "sale_orders"

    id = Column(Integer, primary_key=True)
    odoo_id = Column(Integer, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    partner_id = Column(Integer, ForeignKey("partners.odoo_id"))
    date_order = Column(DateTime)
    amount_total = Column(Float, default=0.0)
    user_id = Column(Integer)

    partner = relationship("Partner", back_populates="sale_orders")
    lines = relationship("SaleOrderLine", back_populates="order")


class SaleOrderLine(Base):
    __tablename__ = "sale_order_lines"

    id = Column(Integer, primary_key=True)
    odoo_id = Column(Integer, unique=True, index=True, nullable=False)
    order_id = Column(Integer, ForeignKey("sale_orders.odoo_id"))
    product_id = Column(Integer, ForeignKey("products.odoo_id"))
    quantity = Column(Float, default=0.0)
    price_unit = Column(Float, default=0.0)

    order = relationship("SaleOrder", back_populates="lines")
    product = relationship("Product", back_populates="sale_order_lines")


# ------------------------
# Purchase Orders
# ------------------------
class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True)
    odoo_id = Column(Integer, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    partner_id = Column(Integer, ForeignKey("partners.odoo_id"))
    date_order = Column(DateTime)
    amount_total = Column(Float, default=0.0)
    user_id = Column(Integer)

    partner = relationship("Partner", back_populates="purchase_orders")
    lines = relationship("PurchaseOrderLine", back_populates="order")


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"

    id = Column(Integer, primary_key=True)
    odoo_id = Column(Integer, unique=True, index=True, nullable=False)
    order_id = Column(Integer, ForeignKey("purchase_orders.odoo_id"))
    product_id = Column(Integer, ForeignKey("products.odoo_id"))
    quantity = Column(Float, default=0.0)
    price_unit = Column(Float, default=0.0)

    order = relationship("PurchaseOrder", back_populates="lines")
    product = relationship("Product", back_populates="purchase_order_lines")


# ------------------------
# Indexes for performance
# ------------------------
Index("ix_products_default_code", Product.default_code)
Index("ix_sale_orders_date_order", SaleOrder.date_order)
Index("ix_purchase_orders_date_order", PurchaseOrder.date_order)
Index("ix_production_orders_date_start", ProductionOrder.date_planned_start)
Index("ix_inventory_quants_product", InventoryQuant.product_id)
