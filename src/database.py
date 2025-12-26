"""Konfiguracja bazy danych."""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Bazowa klasa dla modeli SQLAlchemy."""

    pass


def get_db():
    """Dependency do uzyskania sesji bazy danych."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Inicjalizacja bazy danych (tworzenie tabel)."""
    Base.metadata.create_all(bind=engine)
