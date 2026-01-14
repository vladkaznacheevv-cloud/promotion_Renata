def test_basic():
    assert True
def test_imports():
    try:
        from core.models import User, Base
        from core.database import engine, AsyncSessionLocal
        assert True
    except Exception as e:
        assert False, f"Fatal import main: {e}"