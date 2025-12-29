"""Serwis autentykacji - hashowanie hasel i weryfikacja uzytkownikow."""

from typing import Optional

import bcrypt
from sqlalchemy.orm import Session

from ..models import User


class AuthService:
    """Serwis do obslugi autentykacji."""

    def __init__(self, db: Session):
        self.db = db

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

    def authenticate(self, username: str, password: str) -> Optional[User]:
        """Uwierzytelnij uzytkownika. Zwraca User jesli sukces, None jesli blad."""
        user = self.db.query(User).filter(User.username == username).first()

        if not user:
            return None

        if not user.is_active:
            return None

        if not self.verify_password(password, user.hashed_password):
            return None

        return user

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Pobierz uzytkownika po ID."""
        return self.db.query(User).filter(User.id == user_id).first()

    def create_user(
        self,
        username: str,
        password: str,
        email: Optional[str] = None,
        is_superuser: bool = False,
    ) -> User:
        """Utworz nowego uzytkownika."""
        user = User(
            username=username,
            email=email,
            hashed_password=self.hash_password(password),
            is_superuser=is_superuser,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
