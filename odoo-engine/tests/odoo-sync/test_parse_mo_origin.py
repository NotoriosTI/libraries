import pytest

from odoo_engine.sync_manager.sync_manager import SyncManager


class TestParseMoOrigin:
    @pytest.mark.parametrize(
        "name, expected",
        [
            ("WH/MO/00123_AUTO", "AUTO"),
            ("WH/MO/00123_CHAT", "CHAT"),
            ("WH/MO/00123", None),
            (None, None),
            ("", None),
        ],
    )
    def test_parse_mo_origin(self, name, expected):
        assert SyncManager._parse_mo_origin(name) == expected
