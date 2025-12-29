"""Skrypt do tworzenia administratorow systemu.

Uzycie:
    python scripts/create_admin.py <username> <password>

Przyklad:
    python scripts/create_admin.py admin tajnehaslo123
"""

import sys
from pathlib import Path

# Dodaj katalog projektu do sciezki
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import SessionLocal, init_db
from src.services.auth import AuthService
from src.models import User


def create_admin(username: str, password: str, is_superuser: bool = True):
    """Utworz nowego administratora."""
    init_db()
    db = SessionLocal()

    try:
        # Sprawdz czy uzytkownik juz istnieje
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            print(f"Blad: Uzytkownik '{username}' juz istnieje!")
            sys.exit(1)

        # Utworz uzytkownika
        auth = AuthService(db)
        user = auth.create_user(
            username=username,
            password=password,
            is_superuser=is_superuser,
        )

        print(f"Sukces! Utworzono administratora: {user.username}")
        print(f"  ID: {user.id}")
        print(f"  Superuser: {user.is_superuser}")
        print(f"\nMozesz teraz zalogowac sie na http://localhost:8000/login")

    finally:
        db.close()


def list_admins():
    """Wyswietl liste administratorow."""
    init_db()
    db = SessionLocal()

    try:
        users = db.query(User).all()

        if not users:
            print("Brak administratorow w bazie danych.")
            print("Uzyj: python scripts/create_admin.py <username> <password>")
            return

        print("Lista administratorow:")
        print("-" * 50)
        for user in users:
            status = "aktywny" if user.is_active else "nieaktywny"
            superuser = " (superuser)" if user.is_superuser else ""
            last_login = user.last_login.strftime("%Y-%m-%d %H:%M") if user.last_login else "nigdy"
            print(f"  {user.id}. {user.username}{superuser} - {status}")
            print(f"     Ostatnie logowanie: {last_login}")
        print("-" * 50)
        print(f"Razem: {len(users)} uzytkownikow")

    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) == 1:
        # Bez argumentow - pokaz liste
        list_admins()
    elif len(sys.argv) == 2 and sys.argv[1] in ("--list", "-l"):
        list_admins()
    elif len(sys.argv) == 3:
        username = sys.argv[1]
        password = sys.argv[2]

        if len(password) < 6:
            print("Blad: Haslo musi miec co najmniej 6 znakow!")
            sys.exit(1)

        create_admin(username, password)
    else:
        print(__doc__)
        sys.exit(1)
