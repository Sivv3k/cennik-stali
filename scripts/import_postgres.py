#!/usr/bin/env python3
"""Import danych z JSON do PostgreSQL."""

import json
import sys
from pathlib import Path

# Dodaj ścieżkę projektu
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from src.database import SessionLocal, engine
from src.models import (
    Material,
    Dimension,
    BasePrice,
    ThicknessModifier,
    WidthModifier,
    ExchangeRate,
    GrindingPrice,
    FilmPrice,
    ProcessingOption,
    User,
    GrindingProvider,
    FilmType,
    SurfaceFinish,
)


# Mapowanie tabel na modele (w kolejności dla FK)
TABLE_MODEL_MAP = {
    "users": User,
    "materials": Material,
    "dimensions": Dimension,
    "exchange_rates": ExchangeRate,
    "thickness_modifiers": ThicknessModifier,
    "width_modifiers": WidthModifier,
    "base_prices": BasePrice,
    "grinding_prices": GrindingPrice,
    "film_prices": FilmPrice,
    "processing_options": ProcessingOption,
}

# Pola enum wymagające konwersji
ENUM_FIELDS = {
    "grinding_prices": {
        "provider": GrindingProvider,
    },
    "film_prices": {
        "film_type": FilmType,
    },
    "base_prices": {
        "surface_finish": SurfaceFinish,
    },
}


def convert_enums(table: str, row: dict) -> dict:
    """Konwertuj stringi na enumy."""
    if table not in ENUM_FIELDS:
        return row

    for field, enum_class in ENUM_FIELDS[table].items():
        if field in row and row[field] is not None:
            try:
                row[field] = enum_class(row[field])
            except ValueError:
                print(f"  UWAGA: Nieznana wartość enum {field}={row[field]}")
                # Spróbuj znaleźć po nazwie
                for e in enum_class:
                    if e.name == row[field] or e.value == row[field]:
                        row[field] = e
                        break

    return row


def import_data(input_path: str = "data_export.json"):
    """Importuj dane z JSON do PostgreSQL."""
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    db = SessionLocal()

    try:
        # Wyczyść tabele (w odwrotnej kolejności dla FK)
        print("Czyszczenie tabel...")
        for table in reversed(list(TABLE_MODEL_MAP.keys())):
            if table in data:
                db.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
        db.commit()

        # Importuj dane (w kolejności dla FK)
        for table, model in TABLE_MODEL_MAP.items():
            if table not in data:
                continue

            rows = data[table]
            if not rows:
                print(f"  {table}: 0 rekordów (pominięto)")
                continue

            print(f"  {table}: importowanie {len(rows)} rekordów...")

            for row in rows:
                # Konwertuj enumy
                row = convert_enums(table, row)

                # Usuń puste/None wartości dla boolean (SQLite->PG)
                for key, value in list(row.items()):
                    if value == "":
                        row[key] = None

                try:
                    obj = model(**row)
                    db.add(obj)
                except Exception as e:
                    print(f"    BŁĄD przy rekordzie {row}: {e}")
                    continue

            db.commit()

        # Zresetuj sekwencje
        print("\nResetowanie sekwencji...")
        for table in TABLE_MODEL_MAP.keys():
            if table in data and data[table]:
                db.execute(text(f"""
                    SELECT setval(pg_get_serial_sequence('{table}', 'id'),
                           COALESCE((SELECT MAX(id) FROM {table}), 1))
                """))
        db.commit()

        print("\nImport zakończony!")

    except Exception as e:
        print(f"BŁĄD: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import_data()
