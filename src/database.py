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
    """Inicjalizacja bazy danych (tworzenie tabel i admina)."""
    import bcrypt
    from .models.user import User, UserRole

    # Utwórz wszystkie tabele
    Base.metadata.create_all(bind=engine)

    # Utwórz domyślnego admina jeśli brak użytkowników
    db = SessionLocal()
    try:
        user_count = db.query(User).count()
        if user_count == 0:
            # Hashuj hasło
            password = "admin123"
            salt = bcrypt.gensalt()
            hashed = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

            admin = User(
                username="admin",
                hashed_password=hashed,
                role=UserRole.ADMIN.value,
                must_change_password=True,  # Wymuś zmianę przy pierwszym logowaniu
            )
            db.add(admin)
            db.commit()
            print("=" * 50)
            print("UTWORZONO DOMYŚLNE KONTO ADMINISTRATORA:")
            print("  Login: admin")
            print("  Hasło: admin123")
            print("  ZMIEŃ HASŁO PO PIERWSZYM LOGOWANIU!")
            print("=" * 50)
    finally:
        db.close()
