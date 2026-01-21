import os
import importlib
from unittest.mock import patch


def test_imports():
    """Тест импортов основных модулей (под текущую архитектуру)"""
    from core.database import Base
    from core.users.models import User
    from core.consultations.models import Consultation, UserConsultation

    assert Base is not None
    assert User is not None
    assert Consultation is not None
    assert UserConsultation is not None


def test_models_exist():
    """Тест существования основных моделей"""
    from core.users.models import User
    from core.consultations.models import Consultation, UserConsultation

    assert User.__tablename__ == "users"
    assert Consultation.__tablename__ == "consultations"
    assert UserConsultation.__tablename__ == "user_consultations"


def test_database_config():
    """Тест конфигурации базы данных: engine должен создаваться при env"""
    with patch.dict(os.environ, {
        "DB_USER": "test",
        "DB_PASSWORD": "test",
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "DB_NAME": "test_db",
    }):
        import core.database as db
        importlib.reload(db)
        assert db.engine is not None


def test_basic():
    assert True