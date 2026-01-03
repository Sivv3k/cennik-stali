"""Model maszyn CTL/Multiblanking - ATH i RBI."""

from enum import Enum
from typing import Optional

from sqlalchemy import String, Float, Boolean, Enum as SQLEnum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class MachineType(str, Enum):
    """Typy maszyn."""
    ATH = "ATH"  # CTL do 12mm, do 2000mm szerokości
    RBI = "RBI"  # RedBud - CTL + Multiblanking, do 3mm, do 1500mm


class OperationType(str, Enum):
    """Typy operacji."""
    CTL = "CTL"  # Cut To Length - cięcie na długość
    MULTIBLANKING = "MULTIBLANKING"  # Cięcie na długość i szerokość


# Limity maszyn
MACHINE_LIMITS = {
    MachineType.ATH: {
        "max_thickness": 12.0,
        "max_width": 2000.0,
        "operations": [OperationType.CTL],
    },
    MachineType.RBI: {
        "max_thickness": 3.0,
        "max_width": 1500.0,
        "operations": [OperationType.CTL, OperationType.MULTIBLANKING],
    },
}

# Dostępne szerokości źródłowe dla multiblankingu
SOURCE_WIDTHS = [1000, 1250, 1500]


class MachinePrice(Base):
    """Cennik dopłat za maszynę CTL/Multiblanking.

    Dopłata PLN/kg zależna od:
    - typu maszyny (ATH/RBI)
    - typu operacji (CTL/Multiblanking)
    - grubości materiału
    """

    __tablename__ = "machine_prices"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Maszyna
    machine_type: Mapped[MachineType] = mapped_column(
        SQLEnum(MachineType), index=True
    )

    # Typ operacji
    operation_type: Mapped[OperationType] = mapped_column(
        SQLEnum(OperationType), index=True
    )

    # Grubość materiału
    thickness: Mapped[float] = mapped_column(Float, index=True)

    # Dopłata PLN/kg
    surcharge_pln_per_kg: Mapped[float] = mapped_column(Float)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Uwagi
    notes: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Unikalność kombinacji
    __table_args__ = (
        UniqueConstraint(
            'machine_type', 'operation_type', 'thickness',
            name='uq_machine_price'
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<MachinePrice {self.machine_type.value} {self.operation_type.value} "
            f"{self.thickness}mm @ +{self.surcharge_pln_per_kg} PLN/kg>"
        )


def get_available_machines(thickness: float, width: float) -> list[MachineType]:
    """Zwróć listę dostępnych maszyn dla podanych parametrów."""
    available = []

    for machine, limits in MACHINE_LIMITS.items():
        if thickness <= limits["max_thickness"] and width <= limits["max_width"]:
            available.append(machine)

    return available


def can_do_multiblanking(thickness: float, width: float) -> bool:
    """Sprawdź czy multiblanking jest dostępny."""
    rbi_limits = MACHINE_LIMITS[MachineType.RBI]
    return thickness <= rbi_limits["max_thickness"] and width <= rbi_limits["max_width"]


def optimize_source_width(target_width: float) -> dict:
    """Znajdź optymalną szerokość źródłową dla multiblankingu.

    Returns:
        dict z: source_width, pieces_per_sheet, waste_mm, utilization_pct
    """
    best = None

    for source_width in SOURCE_WIDTHS:
        if target_width > source_width:
            continue

        pieces = int(source_width // target_width)
        if pieces == 0:
            continue

        waste = source_width - (pieces * target_width)
        utilization = (pieces * target_width) / source_width * 100

        option = {
            "source_width": source_width,
            "pieces_per_sheet": pieces,
            "waste_mm": waste,
            "utilization_pct": round(utilization, 1),
        }

        # Wybierz opcję z najwyższym wykorzystaniem
        if best is None or option["utilization_pct"] > best["utilization_pct"]:
            best = option

    return best


def calculate_all_source_options(target_width: float) -> list[dict]:
    """Oblicz wszystkie opcje szerokości źródłowej."""
    options = []

    for source_width in SOURCE_WIDTHS:
        if target_width > source_width:
            continue

        pieces = int(source_width // target_width)
        if pieces == 0:
            continue

        waste = source_width - (pieces * target_width)
        utilization = (pieces * target_width) / source_width * 100

        options.append({
            "source_width": source_width,
            "pieces_per_sheet": pieces,
            "waste_mm": waste,
            "utilization_pct": round(utilization, 1),
        })

    return options
