"""Serwis autentykacji - hashowanie hasel, weryfikacja i zarządzanie użytkownikami."""

from datetime import datetime, timedelta
from typing import Optional, List

import bcrypt
from sqlalchemy.orm import Session

from ..models import User, UserRole, ApiKey
from ..auth.permissions import hash_api_key, generate_api_key


class AuthService:
    """Serwis do obslugi autentykacji i zarządzania użytkownikami."""

    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 15

    def __init__(self, db: Session):
        self.db = db

    # ============== PASSWORD HASHING ==============

    def hash_password(self, password: str) -> str:
        """Hashuj haslo przy uzyciu bcrypt."""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Zweryfikuj haslo."""
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )

    # ============== AUTHENTICATION ==============

    def authenticate(self, username: str, password: str) -> Optional[User]:
        """Uwierzytelnij uzytkownika. Zwraca User jesli sukces, None jesli blad."""
        user = self.db.query(User).filter(User.username == username).first()

        if not user:
            return None

        if not user.is_active:
            return None

        # Sprawdź blokadę konta
        if user.is_locked:
            return None

        if not self.verify_password(password, user.hashed_password):
            # Zwiększ licznik nieudanych prób
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= self.MAX_FAILED_ATTEMPTS:
                user.locked_until = datetime.utcnow() + timedelta(minutes=self.LOCKOUT_DURATION_MINUTES)
            self.db.commit()
            return None

        # Reset licznika po udanym logowaniu
        user.failed_login_attempts = 0
        user.locked_until = None
        self.db.commit()

        return user

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Pobierz uzytkownika po ID."""
        return self.db.query(User).filter(User.id == user_id).first()

    # ============== USER CRUD ==============

    def list_users(self) -> List[User]:
        """Lista wszystkich użytkowników."""
        return self.db.query(User).order_by(User.created_at.desc()).all()

    def get_user(self, user_id: int) -> Optional[User]:
        """Pobierz użytkownika po ID."""
        return self.db.query(User).filter(User.id == user_id).first()

    def create_user(
        self,
        username: str,
        password: str,
        email: Optional[str] = None,
        role: UserRole = UserRole.VIEWER,
        created_by_id: Optional[int] = None,
        must_change_password: bool = False,
    ) -> User:
        """Utworz nowego uzytkownika."""
        # Sprawdź czy username już istnieje
        existing = self.db.query(User).filter(User.username == username.lower()).first()
        if existing:
            raise ValueError(f"Użytkownik '{username}' już istnieje")

        user = User(
            username=username.lower(),
            email=email,
            hashed_password=self.hash_password(password),
            role=role.value,
            created_by_id=created_by_id,
            must_change_password=must_change_password,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_user(
        self,
        user_id: int,
        email: Optional[str] = None,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[User]:
        """Aktualizuj użytkownika."""
        user = self.get_user(user_id)
        if not user:
            return None

        if email is not None:
            user.email = email
        if role is not None:
            user.role = role.value
        if is_active is not None:
            user.is_active = is_active
            # Przy aktywacji zresetuj blokadę
            if is_active:
                user.failed_login_attempts = 0
                user.locked_until = None

        self.db.commit()
        self.db.refresh(user)
        return user

    def delete_user(self, user_id: int) -> bool:
        """Usuń użytkownika."""
        user = self.get_user(user_id)
        if not user:
            return False

        self.db.delete(user)
        self.db.commit()
        return True

    def reset_password(
        self,
        user_id: int,
        new_password: str,
        must_change: bool = True,
    ) -> Optional[User]:
        """Reset hasła użytkownika przez admina."""
        user = self.get_user(user_id)
        if not user:
            return None

        user.hashed_password = self.hash_password(new_password)
        user.must_change_password = must_change
        user.failed_login_attempts = 0
        user.locked_until = None

        self.db.commit()
        self.db.refresh(user)
        return user

    def change_password(
        self,
        user_id: int,
        current_password: str,
        new_password: str,
    ) -> tuple[bool, str]:
        """Zmiana hasła przez użytkownika. Zwraca (success, message)."""
        user = self.get_user(user_id)
        if not user:
            return False, "Użytkownik nie znaleziony"

        if not self.verify_password(current_password, user.hashed_password):
            return False, "Nieprawidłowe obecne hasło"

        user.hashed_password = self.hash_password(new_password)
        user.must_change_password = False

        self.db.commit()
        return True, "Hasło zmienione"

    def unlock_user(self, user_id: int) -> Optional[User]:
        """Odblokuj konto użytkownika."""
        user = self.get_user(user_id)
        if not user:
            return None

        user.failed_login_attempts = 0
        user.locked_until = None

        self.db.commit()
        self.db.refresh(user)
        return user

    # ============== API KEY CRUD ==============

    def list_api_keys(self, user_id: Optional[int] = None) -> List[ApiKey]:
        """Lista kluczy API (opcjonalnie filtrowana po użytkowniku)."""
        query = self.db.query(ApiKey)
        if user_id:
            query = query.filter(ApiKey.user_id == user_id)
        return query.order_by(ApiKey.created_at.desc()).all()

    def create_api_key(
        self,
        user_id: int,
        name: str,
        permissions: str = "read",
        expires_in_days: Optional[int] = None,
    ) -> tuple[ApiKey, str]:
        """Utwórz nowy klucz API. Zwraca (ApiKey, raw_key)."""
        # Sprawdź czy użytkownik istnieje
        user = self.get_user(user_id)
        if not user:
            raise ValueError("Użytkownik nie znaleziony")

        # Generuj klucz
        raw_key = generate_api_key()
        key_hash = hash_api_key(raw_key)
        key_prefix = raw_key[:8]

        # Oblicz datę wygaśnięcia
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        api_key = ApiKey(
            user_id=user_id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            name=name,
            permissions=permissions,
            expires_at=expires_at,
        )

        self.db.add(api_key)
        self.db.commit()
        self.db.refresh(api_key)

        return api_key, raw_key

    def delete_api_key(self, key_id: int) -> bool:
        """Usuń klucz API."""
        api_key = self.db.query(ApiKey).filter(ApiKey.id == key_id).first()
        if not api_key:
            return False

        self.db.delete(api_key)
        self.db.commit()
        return True

    def deactivate_api_key(self, key_id: int) -> Optional[ApiKey]:
        """Dezaktywuj klucz API (bez usuwania)."""
        api_key = self.db.query(ApiKey).filter(ApiKey.id == key_id).first()
        if not api_key:
            return None

        api_key.is_active = False
        self.db.commit()
        self.db.refresh(api_key)
        return api_key
