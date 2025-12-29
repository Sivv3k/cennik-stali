"""Model materiału - rozbudowany dla różnych typów stali i aluminium."""

from enum import Enum
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Float, Enum as SQLEnum, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .price import BasePrice
    from .processing import GrindingPrice


class MaterialCategory(str, Enum):
    """Kategorie materiałów."""

    STAINLESS_STEEL = "stal_nierdzewna"  # 1.4301, 1.4404, 1.4016
    CARBON_STEEL = "stal_czarna"          # DC01, S235, S355
    ALUMINUM = "aluminium"                 # 1050, 5754, 6061


class SurfaceFinish(str, Enum):
    """Typy wykończenia powierzchni."""

    # Stal nierdzewna
    FINISH_2B = "2B"              # Zimnowalcowana, wytrawiowana (standard)
    FINISH_BA = "BA"              # Jasna wyżarzona (bright annealed)
    FINISH_1D = "1D"              # Gorącowalcowana, wytrawiowana
    FINISH_LEN = "LEN"            # Wykończenie lniane
    FINISH_RYFEL = "RYFEL ASTM"   # Blacha ryflowana

    # Stal czarna
    FINISH_HR = "HR"              # Hot rolled
    FINISH_CR = "CR"              # Cold rolled
    FINISH_PICKLED = "trawiona"   # Pickled
    FINISH_OILED = "naoliwiona"   # Oiled

    # Aluminium
    FINISH_MILL = "mill"          # Mill finish
    FINISH_ANODIZED = "anodowana" # Anodized


class MaterialGroup(Base):
    """Grupa materiałów (np. Austenityczne, Ferrytyczne)."""

    __tablename__ = "material_groups"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Identyfikacja
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    category: Mapped[MaterialCategory] = mapped_column(SQLEnum(MaterialCategory))

    # Opis grupy
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Kolejność wyświetlania
    display_order: Mapped[int] = mapped_column(default=0)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relacje
    materials: Mapped[list["Material"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<MaterialGroup {self.name} ({self.category.value})>"


class Material(Base):
    """Model materiału (gatunek stali/aluminium)."""

    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Grupa materiału
    group_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("material_groups.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Identyfikacja
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    category: Mapped[MaterialCategory] = mapped_column(SQLEnum(MaterialCategory))

    # Gatunek wg normy (np. 1.4301, 1.4404, DC01)
    grade: Mapped[str] = mapped_column(String(50), index=True)

    # Norma (np. EN 10088-2 dla nierdzewnej)
    standard: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Odpowiedniki (np. AISI 304 dla 1.4301)
    equivalent_grades: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Skład chemiczny (główne składniki)
    composition: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)

    # Parametry fizyczne
    density: Mapped[float] = mapped_column(Float, default=7.9)  # g/cm³ (stal)

    # Właściwości mechaniczne
    tensile_strength: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Rm [MPa]
    yield_strength: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)    # Rp0.2 [MPa]

    # Zastosowania
    applications: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Opis
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Kolejność wyświetlania
    display_order: Mapped[int] = mapped_column(default=0)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relacje
    group: Mapped[Optional["MaterialGroup"]] = relationship(back_populates="materials")
    base_prices: Mapped[list["BasePrice"]] = relationship(
        back_populates="material", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Material {self.grade} ({self.category.value})>"


class Dimension(Base):
    """Dostępne wymiary (grubość x szerokość x długość)."""

    __tablename__ = "dimensions"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Wymiary w mm
    thickness: Mapped[float] = mapped_column(Float, index=True)
    width: Mapped[float] = mapped_column(Float, index=True)
    length: Mapped[float] = mapped_column(Float, index=True)

    # Czy standardowy wymiar
    is_standard: Mapped[bool] = mapped_column(Boolean, default=True)

    # Waga arkusza w kg (obliczana)
    weight_per_sheet: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"<Dimension {self.thickness}x{self.width}x{self.length}>"


# Predefiniowane wymiary standardowe
STANDARD_THICKNESSES = [
    0.4, 0.5, 0.6, 0.7, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5, 3.0,
    4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 15.0, 16.0, 18.0, 20.0,
    25.0, 30.0, 40.0, 45.0, 50.0
]

STANDARD_WIDTHS = [1000, 1250, 1500, 2000]
STANDARD_LENGTHS = [2000, 2500, 3000, 6000]

# Mapowanie szerokości do długości
WIDTH_LENGTH_MAP = {
    1000: 2000,
    1250: 2500,
    1500: 3000,
    2000: 6000,
}
