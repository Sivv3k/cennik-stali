"""Model cennika - ceny bazowe i modyfikatory."""

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    String, Float, Integer, ForeignKey, DateTime, Boolean,
    UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .material import Material, SurfaceFinish


class BasePrice(Base):
    """Cena bazowa materiału (gatunek + powierzchnia + grubość + szerokość).

    Odpowiada kolumnie "z papierem" w Excelu - to jest cena wyjściowa
    do której dodawane są modyfikatory.
    """

    __tablename__ = "base_prices"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Powiązanie z materiałem
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), index=True)
    material: Mapped["Material"] = relationship(back_populates="base_prices")

    # Wykończenie powierzchni (2B, BA, 1D, LEN, RYFEL)
    surface_finish: Mapped[str] = mapped_column(String(20), index=True)

    # Wymiary
    thickness: Mapped[float] = mapped_column(Float, index=True)  # mm
    width: Mapped[float] = mapped_column(Float, index=True)      # mm
    length: Mapped[float] = mapped_column(Float)                  # mm

    # Cena bazowa PLN/kg (kolumna "z papierem")
    price_pln_per_kg: Mapped[float] = mapped_column(Float)

    # Waluta i daty
    valid_from: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Uwagi (np. "NIE SZLIFUJEMY")
    notes: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Unikalność: materiał + powierzchnia + grubość + szerokość + data
    __table_args__ = (
        UniqueConstraint(
            'material_id', 'surface_finish', 'thickness', 'width', 'valid_from',
            name='uq_base_price'
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<BasePrice {self.material_id} {self.surface_finish} "
            f"{self.thickness}mm {self.width}mm @ {self.price_pln_per_kg} PLN/kg>"
        )


class ThicknessModifier(Base):
    """Modyfikator ceny za grubość.

    Dla różnych kombinacji gatunek+powierzchnia są różne dodatki
    za konkretne grubości (z arkusza "DANE DO WPROWADZENIA").
    """

    __tablename__ = "thickness_modifiers"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Klucz: gatunek + powierzchnia + szerokość bazowa
    grade: Mapped[str] = mapped_column(String(50), index=True)
    surface_finish: Mapped[str] = mapped_column(String(20), index=True)
    base_width: Mapped[float] = mapped_column(Float, default=1000)  # szerokość bazowa

    # Grubość i dodatek
    thickness: Mapped[float] = mapped_column(Float, index=True)
    price_modifier: Mapped[float] = mapped_column(Float)  # PLN/kg (+ lub -)

    __table_args__ = (
        UniqueConstraint(
            'grade', 'surface_finish', 'base_width', 'thickness',
            name='uq_thickness_modifier'
        ),
    )


class WidthModifier(Base):
    """Modyfikator ceny za szerokość.

    Dodatki za szerokość większą niż bazowa (1000mm).
    """

    __tablename__ = "width_modifiers"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Klucz: gatunek (opcjonalnie) + szerokość
    grade: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    width: Mapped[float] = mapped_column(Float, index=True)

    # Dodatek PLN/kg
    price_modifier: Mapped[float] = mapped_column(Float)

    __table_args__ = (
        UniqueConstraint('grade', 'width', name='uq_width_modifier'),
    )


class ExchangeRate(Base):
    """Kursy walut."""

    __tablename__ = "exchange_rates"

    id: Mapped[int] = mapped_column(primary_key=True)

    currency_from: Mapped[str] = mapped_column(String(3), default="EUR")
    currency_to: Mapped[str] = mapped_column(String(3), default="PLN")
    rate: Mapped[float] = mapped_column(Float)

    valid_from: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self) -> str:
        return f"<ExchangeRate {self.currency_from}/{self.currency_to} = {self.rate}>"
