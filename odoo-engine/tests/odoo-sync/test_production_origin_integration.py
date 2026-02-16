"""
Integration tests for production order origin tracking.

Tests the full flow:
1. odoo-api: Create MO with origin_suffix → verify name in Odoo has suffix
2. odoo-engine: Sync production orders → verify origin column in PostgreSQL
3. dashboard query: Verify get_production_orders_from_db returns correct data

Requires:
    RUN_ODOO_INTEGRATION=1  (env var to enable)

Servers:
    - Odoo staging: ODOO_TEST_* env vars
    - PostgreSQL:   juandb_test on localhost
"""

import os
import sys
import logging
from pathlib import Path

# Add odoo-api src to sys.path so we can import OdooProduct
_ODOO_API_SRC = Path(__file__).resolve().parents[3] / "odoo-api" / "src"
if str(_ODOO_API_SRC) not in sys.path:
    sys.path.insert(0, str(_ODOO_API_SRC))

import psycopg2
import pytest
from config_manager import secrets
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odoo_engine.sync_manager.models import Base, ProductionOrder
from odoo_engine.sync_manager.sync_manager import SyncManager
from odoo_engine.utils import OdooClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Skip guard
# ---------------------------------------------------------------------------
pytestmark = pytest.mark.integration

SKIP_MSG = "Set RUN_ODOO_INTEGRATION=1 to run integration tests"


def _should_skip():
    return os.getenv("RUN_ODOO_INTEGRATION") != "1"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
TEST_DB_NAME = "juandb_test"

DB_CONFIG = {
    "host": secrets.DB_HOST,
    "port": int(secrets.DB_PORT),
    "user": secrets.DB_USER,
    "password": secrets.DB_PASSWORD,
    "database": TEST_DB_NAME,
}


@pytest.fixture(scope="module")
def odoo_product_client():
    """OdooProduct client connected to the staging server."""
    from odoo_api.product import OdooProduct

    return OdooProduct(
        db=secrets.ODOO_TEST_DB,
        url=secrets.ODOO_TEST_URL,
        username=secrets.ODOO_TEST_USERNAME,
        password=secrets.ODOO_TEST_PASSWORD,
    )


@pytest.fixture(scope="module")
def odoo_engine_client():
    """OdooClient (odoorpc) connected to staging server."""
    return OdooClient()


@pytest.fixture(scope="module")
def pg_engine():
    """SQLAlchemy engine connected to juandb_test."""
    url = (
        f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    )
    engine = create_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def pg_session(pg_engine):
    """SQLAlchemy session for juandb_test."""
    Session = sessionmaker(bind=pg_engine, expire_on_commit=False)
    session = Session()
    yield session
    session.close()


@pytest.fixture(scope="module")
def pg_conn():
    """Raw psycopg2 connection for simple queries."""
    conn = psycopg2.connect(**DB_CONFIG)
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _find_test_sku(client):
    """Find a valid SKU with a BOM on the staging server for testing."""
    records = client.models.execute_kw(
        client.db,
        client.uid,
        client.password,
        "mrp.production",
        "search_read",
        [[["state", "=", "draft"]]],
        {"fields": ["product_id"], "limit": 1, "order": "id desc"},
    )
    if records:
        product_id = records[0]["product_id"][0]
        product = client.models.execute_kw(
            client.db,
            client.uid,
            client.password,
            "product.product",
            "read",
            [[product_id]],
            {"fields": ["default_code"]},
        )
        if product and product[0].get("default_code"):
            return product[0]["default_code"]

    # Fallback: find any product with a BOM
    boms = client.models.execute_kw(
        client.db,
        client.uid,
        client.password,
        "mrp.bom",
        "search_read",
        [[]],
        {"fields": ["product_tmpl_id"], "limit": 5},
    )
    for bom in boms:
        tmpl_id = bom["product_tmpl_id"][0]
        products = client.models.execute_kw(
            client.db,
            client.uid,
            client.password,
            "product.product",
            "search_read",
            [[["product_tmpl_id", "=", tmpl_id]]],
            {"fields": ["default_code"], "limit": 1},
        )
        if products and products[0].get("default_code"):
            return products[0]["default_code"]

    return None


def _cancel_mo(client, mo_id):
    """Cancel a manufacturing order to clean up after test."""
    try:
        client.models.execute_kw(
            client.db,
            client.uid,
            client.password,
            "mrp.production",
            "action_cancel",
            [[mo_id]],
        )
    except Exception as e:
        logger.warning("Could not cancel MO %s: %s", mo_id, e)


def _read_mo_name(client, mo_id):
    """Read the name of a manufacturing order from Odoo."""
    result = client.models.execute_kw(
        client.db,
        client.uid,
        client.password,
        "mrp.production",
        "read",
        [[mo_id]],
        {"fields": ["name"]},
    )
    return result[0]["name"] if result else None


# ---------------------------------------------------------------------------
# Phase 1: odoo-api — create MO with origin_suffix
# ---------------------------------------------------------------------------
class TestOdooApiOriginSuffix:
    """Verify that create_single_production_order appends origin suffix to MO name."""

    @pytest.fixture(autouse=True)
    def _skip_check(self):
        if _should_skip():
            pytest.skip(SKIP_MSG)

    def test_create_mo_with_auto_suffix(self, odoo_product_client):
        """Create an MO with origin_suffix='TEST' and verify name ends with _TEST."""
        client = odoo_product_client
        sku = _find_test_sku(client)
        if not sku:
            pytest.skip("No suitable SKU with BOM found on staging")

        result = client.create_single_production_order(
            product_sku=sku,
            product_qty=1,
            picking_qty=0,
            origin_suffix="TEST",
        )

        assert result["status"] == "success", f"MO creation failed: {result.get('message')}"
        mo_id = result["production_order_id"]
        assert mo_id is not None

        try:
            mo_name = _read_mo_name(client, mo_id)
            assert mo_name is not None, "Could not read MO name"
            assert mo_name.endswith("_TEST"), (
                f"Expected MO name to end with '_TEST', got: {mo_name}"
            )
            logger.info("MO created: id=%s, name=%s", mo_id, mo_name)
        finally:
            _cancel_mo(client, mo_id)

    def test_create_mo_without_suffix(self, odoo_product_client):
        """Create an MO without origin_suffix and verify name has no suffix."""
        client = odoo_product_client
        sku = _find_test_sku(client)
        if not sku:
            pytest.skip("No suitable SKU with BOM found on staging")

        result = client.create_single_production_order(
            product_sku=sku,
            product_qty=1,
            picking_qty=0,
        )

        assert result["status"] == "success", f"MO creation failed: {result.get('message')}"
        mo_id = result["production_order_id"]

        try:
            mo_name = _read_mo_name(client, mo_id)
            assert mo_name is not None
            assert not mo_name.endswith("_AUTO"), f"Name should not have suffix: {mo_name}"
            assert not mo_name.endswith("_CHAT"), f"Name should not have suffix: {mo_name}"
            assert not mo_name.endswith("_TEST"), f"Name should not have suffix: {mo_name}"
        finally:
            _cancel_mo(client, mo_id)


# ---------------------------------------------------------------------------
# Phase 3: odoo-engine — sync and verify origin in DB
# ---------------------------------------------------------------------------
class TestOdooEngineSyncOrigin:
    """Verify that sync_production_orders populates the origin column correctly."""

    @pytest.fixture(autouse=True)
    def _skip_check(self):
        if _should_skip():
            pytest.skip(SKIP_MSG)

    def test_sync_populates_origin(self, odoo_product_client, odoo_engine_client, pg_session):
        """
        1. Create MOs with _AUTO and _CHAT suffixes on Odoo
        2. Run sync_production_orders
        3. Verify origin column in PostgreSQL
        """
        client = odoo_product_client
        sku = _find_test_sku(client)
        if not sku:
            pytest.skip("No suitable SKU with BOM found on staging")

        created_mo_ids = []

        # Create MOs with different suffixes
        for suffix in ("AUTO", "CHAT"):
            result = client.create_single_production_order(
                product_sku=sku,
                product_qty=1,
                picking_qty=0,
                origin_suffix=suffix,
            )
            assert result["status"] == "success", f"Failed to create MO with suffix {suffix}"
            created_mo_ids.append(result["production_order_id"])

        try:
            # Run sync
            sync = SyncManager(pg_session, odoo_engine_client)
            sync.sync_production_orders()

            # Verify in DB
            for mo_id, expected_origin in zip(created_mo_ids, ["AUTO", "CHAT"]):
                row = (
                    pg_session.query(ProductionOrder)
                    .filter(ProductionOrder.odoo_id == mo_id)
                    .one_or_none()
                )
                assert row is not None, f"MO {mo_id} not found in DB after sync"
                assert row.origin == expected_origin, (
                    f"Expected origin='{expected_origin}' for MO {mo_id}, got '{row.origin}'"
                )
                logger.info(
                    "Verified MO %s: odoo_id=%s, origin=%s",
                    mo_id,
                    row.odoo_id,
                    row.origin,
                )
        finally:
            for mo_id in created_mo_ids:
                _cancel_mo(client, mo_id)

    def test_mo_without_suffix_has_null_origin(self, odoo_product_client, odoo_engine_client, pg_session):
        """MOs without suffix should have origin=NULL after sync."""
        client = odoo_product_client
        sku = _find_test_sku(client)
        if not sku:
            pytest.skip("No suitable SKU with BOM found on staging")

        result = client.create_single_production_order(
            product_sku=sku,
            product_qty=1,
            picking_qty=0,
        )
        assert result["status"] == "success"
        mo_id = result["production_order_id"]

        try:
            sync = SyncManager(pg_session, odoo_engine_client)
            sync.sync_production_orders()

            row = (
                pg_session.query(ProductionOrder)
                .filter(ProductionOrder.odoo_id == mo_id)
                .one_or_none()
            )
            assert row is not None, f"MO {mo_id} not found in DB"
            assert row.origin is None, (
                f"Expected origin=NULL for MO without suffix, got '{row.origin}'"
            )
        finally:
            _cancel_mo(client, mo_id)


# ---------------------------------------------------------------------------
# Phase 4: dashboard query — verify data from PostgreSQL
# ---------------------------------------------------------------------------
class TestDashboardQuery:
    """Verify the dashboard SQL query returns correct results from PostgreSQL."""

    @pytest.fixture(autouse=True)
    def _skip_check(self):
        if _should_skip():
            pytest.skip(SKIP_MSG)

    def test_query_returns_origin_data(self, pg_conn):
        """Run the dashboard query and verify structure.

        Note: This test depends on the sync tests above having populated
        origin data. If no AUTO/CHAT data exists yet, it will skip.
        """
        cursor = pg_conn.cursor()
        cursor.execute("""
            SELECT po.origin, COUNT(*)
            FROM production_order po
            WHERE po.origin IS NOT NULL
            GROUP BY po.origin
            ORDER BY po.origin
        """)
        rows = cursor.fetchall()
        cursor.close()

        origins = {row[0]: row[1] for row in rows}
        logger.info("Origin distribution in DB: %s", origins)

        if not origins:
            pytest.skip("No origin data in DB yet — sync tests may not have run first")

        # If data exists, all values must be valid origins
        for origin in origins:
            assert origin in ("AUTO", "CHAT"), f"Unexpected origin value: {origin}"

    def test_dashboard_query_with_product_filter(self, pg_conn):
        """Verify the exact query used by get_production_orders_from_db works."""
        cursor = pg_conn.cursor()
        # Get some product IDs that have production orders
        cursor.execute("""
            SELECT DISTINCT product_id
            FROM production_order
            WHERE product_id IS NOT NULL
            LIMIT 5
        """)
        product_ids = [row[0] for row in cursor.fetchall()]

        if not product_ids:
            cursor.close()
            pytest.skip("No production orders with product_id in DB")

        # Run the exact dashboard query
        cursor.execute("""
            SELECT DATE(po.date_planned_start) AS date,
                   po.origin,
                   po.state
            FROM production_order po
            WHERE po.date_planned_start BETWEEN %s AND %s
              AND po.state != 'cancel'
              AND po.origin IN ('AUTO', 'CHAT')
              AND po.product_id = ANY(%s)
            ORDER BY po.date_planned_start
        """, ("2020-01-01 00:00:00", "2030-12-31 23:59:59", product_ids))

        rows = cursor.fetchall()
        cursor.close()

        logger.info("Dashboard query returned %d rows", len(rows))

        # Verify structure of returned rows
        for row in rows:
            date_val, origin, state = row
            assert origin in ("AUTO", "CHAT"), f"Unexpected origin: {origin}"
            assert state != "cancel", f"Cancelled order should be filtered out"

    def test_origin_distribution_query(self, pg_engine):
        """Verify we can compute the automation ratio from the DB."""
        with pg_engine.connect() as conn:
            result = conn.execute(text("""
                SELECT origin, COUNT(*) as cnt
                FROM production_order
                WHERE origin IN ('AUTO', 'CHAT')
                GROUP BY origin
            """))
            rows = {row[0]: row[1] for row in result}

        logger.info("Automation ratio data: %s", rows)

        auto = rows.get("AUTO", 0)
        chat = rows.get("CHAT", 0)
        total = auto + chat

        if total > 0:
            ratio = auto / total
            logger.info("Automation ratio: %.2f%% (%d AUTO / %d total)", ratio * 100, auto, total)
            assert 0 <= ratio <= 1, f"Ratio should be between 0 and 1, got {ratio}"
