import os

os.environ.setdefault("DATABASE_URL", "postgresql://finapp:finapp@localhost:5432/finapp_test")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("ADMIN_EMAIL", "test@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "testpass123")

import pytest
from sqlalchemy import text

from app.database import Base, SessionLocal, engine
from app.categories import DEFAULT_CATEGORIES
from app.models import Category, Subcategory, User
from app.security import hash_password


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    for cat_name, subs in DEFAULT_CATEGORIES.items():
        category = Category(name=cat_name, is_system=True)
        db.add(category)
        db.flush()
        for sub_name in subs:
            db.add(Subcategory(category_id=category.id, name=sub_name))
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def test_user(db_session):
    user = db_session.query(User).filter(User.email == "test@example.com").first()
    if not user:
        user = User(email="test@example.com", password_hash=hash_password("testpass123"))
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user
