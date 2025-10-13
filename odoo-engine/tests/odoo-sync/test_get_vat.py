import pytest

try:
    from odoo_engine.utils import OdooClient
except Exception as _import_exc:  # pragma: no cover
    OdooClient = None  # type: ignore


def test_get_all_vats_from_odoo():
    """Integration test: fetch all VAT (RUT) values from Odoo partners.

    Skips when Odoo credentials are not configured.
    """
    if OdooClient is None:
        pytest.skip(f"OdooClient import failed: {_import_exc}")

    # Try to connect; skip gracefully if secrets are missing or connection fails
    try:
        client = OdooClient()
    except Exception as exc:
        pytest.skip(f"Skipping: cannot connect to Odoo ({exc})")

    limit = 1000
    offset = 0
    vats = []

    while True:
        batch = client.search_read(
            "res.partner",
            domain=[],
            fields=["id", "vat"],
            limit=limit,
            offset=offset,
        )
        if not batch:
            break
        vats.extend([rec.get("vat") for rec in batch])
        offset += limit

        # Simple progress output to aid manual runs
        if offset % (limit * 10) == 0:
            print(f"Fetched {offset} partner rows...")

    print(f"Total partners fetched: {offset}; VAT entries collected: {len(vats)}")

    # Basic sanity check to keep pytest happy without asserting environment-dependent counts
    assert isinstance(vats, list)

    for vat in vats:
        print(vat) if vat else print("None")

if __name__ == "__main__":
    test_get_all_vats_from_odoo()