"""Zarzadzanie sesjami - podpisywane cookies."""

from typing import Optional

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from fastapi import Request, Response


class SessionManager:
    """Menedzer sesji oparty na podpisywanych cookies."""

    def __init__(self, secret_key: str):
        self.serializer = URLSafeTimedSerializer(secret_key)
        self.cookie_name = "admin_session"
        self.max_age = 86400  # 24 godziny

    def create_session(self, response: Response, user_id: int) -> None:
        """Utworz sesje dla uzytkownika (ustaw cookie)."""
        token = self.serializer.dumps({"user_id": user_id})
        response.set_cookie(
            key=self.cookie_name,
            value=token,
            max_age=self.max_age,
            httponly=True,
            samesite="lax",
        )

    def get_user_id(self, request: Request) -> Optional[int]:
        """Pobierz user_id z sesji. Zwraca None jesli brak lub niewazna sesja."""
        token = request.cookies.get(self.cookie_name)

        if not token:
            return None

        try:
            data = self.serializer.loads(token, max_age=self.max_age)
            return data.get("user_id")
        except (BadSignature, SignatureExpired):
            return None

    def destroy_session(self, response: Response) -> None:
        """Usun sesje (wylogowanie)."""
        response.delete_cookie(self.cookie_name)
