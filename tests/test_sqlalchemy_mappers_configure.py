from __future__ import annotations

import core.models  # noqa: F401
from sqlalchemy.orm import configure_mappers


def test_sqlalchemy_configure_mappers_smoke():
    configure_mappers()
