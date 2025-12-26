"""Model materiału."""

from enum import Enum
from typing import Optional

from sqlalchemy import String, Float, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class MaterialCategory(str, Enum):
    """Kategorie materiałów."""

    STAINLESS_STEEL = "stal_nierdzewna"
    CARBON_STEEL = "stal_czarna"
    ALUMINUM = "aluminium"


class Material(Base):
    """Model materiału (gatunek stali/aluminium)."""

    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Podstawowe informacje
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    category: Mapped[MaterialCategory] = mapped_column(SQLEnum(MaterialCategory))
    grade: Mapped[str] = mapped_column(String(50), index=True)  # np. 304, 316, DC01, 5754

    # Opis
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Parametry fizyczne
    density: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # g/cm³

    # Relacje
    prices: Mapped[list["Price"]] = relationship(back_populates="material")

    def __repr__(self) -> str:
        return f"<Material {self.name} ({self.grade})>"
