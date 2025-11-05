from __future__ import annotations

from sqlalchemy import BigInteger, Integer


PRIMARY_KEY_TYPE = BigInteger().with_variant(Integer(), "sqlite")
