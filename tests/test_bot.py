import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Тест импортов основных модулей"""
    try:
        from core.models import User, Base, Deal
        from core.database import engine, async_session, get_db
        assert True
    except Exception as e:
        assert False, f"Fatal import main: {e}"

def test_models_exist():
    """Тест существования основных моделей"""
    from core.models import User, Deal
    
    # Проверяем атрибуты модели User
    assert hasattr(User, '__tablename__')
    assert User.__tablename__ == 'users'
    assert hasattr(User, 'tg_id')
    assert hasattr(User, 'first_name')
    
    # Проверяем атрибуты модели Deal
    assert hasattr(Deal, '__tablename__')
    assert Deal.__tablename__ == 'deals'
    assert hasattr(Deal, 'user_tg_id')
    assert hasattr(Deal, 'status')

def test_database_config():
    """Тест конфигурации базы данных"""
    from core.database import engine
    assert engine is not None

def test_basic():
    """Базовый тест"""
    assert True