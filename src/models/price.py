"""Model cennika."""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import String, Float, Integer, ForeignKey, DateTime, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class SourceType(str, Enum):
    """Źródło materiału."""

    COIL_CTL = "CTL"                # Cut To Length ze zwoju
    COIL_MULTIBLANKING = "multiblanking"  # Multiblanking ze zwoju
    SHEET = "arkusz"                # Arkusz standardowy


class Price(Base):
    """Model ceny materiału."""

    __tablename__ = "prices"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Powiązanie z materiałem
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), index=True)
    material: Mapped["Material"] = relationship(back_populates="prices")

    # Parametry wymiarowe
    thickness: Mapped[float] = mapped_column(Float, index=True)  # Grubość w mm
    width: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Szerokość w mm
    length: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Długość w mm

    # Źródło
    source_type: Mapped[SourceType] = mapped_column(SQLEnum(SourceType))

    # Powierzchnia (opcjonalnie - FK do surfaces)
    surface_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("surfaces.id"), nullable=True
    )

    # Ceny
    price_per_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # PLN/kg
    price_per_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # PLN/m²
    price_per_piece: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # PLN/szt

    # Waluta i data
    currency: Mapped[str] = mapped_column(String(3), default="PLN")
    valid_from: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Minimalne zamówienie
    min_order_qty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    min_order_unit: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # kg, m², szt

    # Metadane
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<Price {self.material_id} {self.thickness}mm @ {self.price_per_kg} PLN/kg>"
