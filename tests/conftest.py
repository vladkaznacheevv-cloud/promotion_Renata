import sys
import types
import os

import pytest


def _ensure_jose_stub() -> None:
    if "jose" in sys.modules:
        return

    jose_module = types.ModuleType("jose")

    class JWTError(Exception):
        pass

    class _JWT:
        @staticmethod
        def encode(payload, *_args, **_kwargs):
            return str(payload)

        @staticmethod
        def decode(_token, *_args, **_kwargs):
            return {}

    jose_module.JWTError = JWTError
    jose_module.jwt = _JWT()
    sys.modules["jose"] = jose_module


def _ensure_passlib_stub() -> None:
    if "passlib.context" in sys.modules:
        return

    passlib_module = types.ModuleType("passlib")
    context_module = types.ModuleType("passlib.context")

    class CryptContext:
        def __init__(self, *args, **kwargs):
            pass

        def hash(self, value: str) -> str:
            return f"hashed::{value}"

        def verify(self, plain: str, hashed: str) -> bool:
            return hashed == f"hashed::{plain}"

    context_module.CryptContext = CryptContext
    passlib_module.context = context_module
    sys.modules["passlib"] = passlib_module
    sys.modules["passlib.context"] = context_module


_ensure_jose_stub()
_ensure_passlib_stub()


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: optional integration checks (run with RUN_INTEGRATION_TESTS=1)",
    )


def pytest_collection_modifyitems(config, items):
    if os.getenv("RUN_INTEGRATION_TESTS", "0") in {"1", "true", "yes"}:
        return
    skip_integration = pytest.mark.skip(reason="set RUN_INTEGRATION_TESTS=1 to run integration tests")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
