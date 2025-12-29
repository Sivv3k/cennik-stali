"""Konfiguracja bazy danych."""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import QueuePool

from .config import get_settings

settings = get_settings()

# Konfiguracja engine zależna od typu bazy
if "postgresql" in settings.database_url:
    # PostgreSQL - z connection pooling
    engine = create_engine(
        settings.database_url,
        poolclass=QueuePool,
        pool_size=5,          # Liczba stałych połączeń
        max_overflow=10,      # Dodatkowe połączenia w szczycie
        pool_pre_ping=True,   # Sprawdzaj połączenie przed użyciem
        pool_recycle=3600,    # Odnawiaj połączenia co godzinę
    )
else:
    # SQLite - bez poolingu, tylko check_same_thread
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
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
