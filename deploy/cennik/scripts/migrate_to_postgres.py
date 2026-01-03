#!/usr/bin/env python3
"""
Migracja danych z SQLite do PostgreSQL.

Uruchomienie:
    cd /volume2/docker/cennik
    python scripts/migrate_to_postgres.py

Wymagania:
    - Istniejąca baza SQLite z danymi
    - Skonfigurowana baza PostgreSQL (pusta lub z tabelami)
    - Zmienne środowiskowe lub argumenty dla connection strings
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, text, MetaData, Table
from sqlalchemy.orm import sessionmaker


# Tabele do migracji (w kolejności zależności)
TABLES_ORDER = [
    # Podstawowe tabele bez zależności
    "material_groups",
    "materials",
    "dimensions",
    "exchange_rates",
    "processing_options",
    "surfaces",

    # Tabele cen
    "base_prices",
    "thickness_modifiers",
    "width_modifiers",
    "grinding_prices",
    "film_prices",

    # Użytkownicy (przed tabelami audytu)
    "users",

    # Tabele audytu (zależą od users)
    "price_change_audits",
    "import_export_audits",

    # API keys (zależy od users)
    "api_keys",
]


def migrate_table(sqlite_engine, postgres_engine, table_name: str, batch_size: int = 1000) -> int:
    """Migruj pojedynczą tabelę. Zwraca liczbę zmigrowanych wierszy."""

    # Sprawdź czy tabela istnieje w SQLite
    with sqlite_engine.connect() as conn:
        result = conn.execute(text(
            f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"
        ))
        if not result.fetchone():
            print(f"  [POMINIĘTO] Tabela {table_name} nie istnieje w SQLite")
            return 0

    # Pobierz dane z SQLite
    with sqlite_engine.connect() as conn:
        result = conn.execute(text(f"SELECT * FROM {table_name}"))
        rows = result.fetchall()
        columns = result.keys()

    if not rows:
        print(f"  [PUSTE] Tabela {table_name} jest pusta")
        return 0

    # Wyczyść tabelę w PostgreSQL (jeśli istnieje)
    with postgres_engine.connect() as conn:
        try:
            conn.execute(text(f"TRUNCATE TABLE {table_name} CASCADE"))
            conn.commit()
        except Exception:
            # Tabela może nie istnieć - utworzy się automatycznie
            conn.rollback()

    # Wstaw dane do PostgreSQL
    column_names = ", ".join(columns)
    placeholders = ", ".join([f":{col}" for col in columns])
    insert_sql = f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})"

    with postgres_engine.connect() as conn:
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            for row in batch:
                row_dict = dict(zip(columns, row))
                conn.execute(text(insert_sql), row_dict)
        conn.commit()

    print(f"  [OK] Tabela {table_name}: {len(rows)} wierszy")
    return len(rows)


def reset_sequences(postgres_engine, table_name: str):
    """Zresetuj sekwencje auto-increment dla tabeli."""
    with postgres_engine.connect() as conn:
        try:
            conn.execute(text(f"""
                SELECT setval(
                    pg_get_serial_sequence('{table_name}', 'id'),
                    COALESCE((SELECT MAX(id) FROM {table_name}), 1)
                )
            """))
            conn.commit()
        except Exception as e:
            # Tabela może nie mieć kolumny id
            pass


def migrate(
    sqlite_url: str,
    postgres_url: str,
    tables: list = None,
    skip_existing: bool = False,
):
    """Wykonaj migrację danych."""

    print("=" * 60)
    print("MIGRACJA SQLite -> PostgreSQL")
    print("=" * 60)
    print(f"Źródło:  {sqlite_url}")
    print(f"Cel:     {postgres_url[:postgres_url.find('@')]}@...")
    print("=" * 60)

    # Połącz z bazami
    sqlite_engine = create_engine(sqlite_url)
    postgres_engine = create_engine(
        postgres_url,
        pool_pre_ping=True,
    )

    # Utwórz tabele w PostgreSQL (importuj modele)
    print("\n[1/3] Tworzenie struktury tabel w PostgreSQL...")

    # Dodaj ścieżkę do projektu
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

    from src.database import Base
    from src.models import (
        Material, MaterialGroup, Dimension,
        BasePrice, ThicknessModifier, WidthModifier, ExchangeRate,
        GrindingPrice, FilmPrice, ProcessingOption, Surface,
        PriceChangeAudit, ImportExportAudit,
        User, ApiKey,
    )

    Base.metadata.create_all(bind=postgres_engine)
    print("  [OK] Struktura tabel utworzona")

    # Migruj dane
    print("\n[2/3] Migracja danych...")

    tables_to_migrate = tables or TABLES_ORDER
    total_rows = 0

    for table_name in tables_to_migrate:
        try:
            rows = migrate_table(sqlite_engine, postgres_engine, table_name)
            total_rows += rows
        except Exception as e:
            print(f"  [BŁĄD] Tabela {table_name}: {e}")
            if not skip_existing:
                raise

    # Resetuj sekwencje
    print("\n[3/3] Resetowanie sekwencji auto-increment...")

    for table_name in tables_to_migrate:
        reset_sequences(postgres_engine, table_name)

    print("  [OK] Sekwencje zresetowane")

    # Podsumowanie
    print("\n" + "=" * 60)
    print("MIGRACJA ZAKOŃCZONA POMYŚLNIE")
    print(f"Zmigrowano {total_rows} wierszy w {len(tables_to_migrate)} tabelach")
    print("=" * 60)

    return total_rows


def main():
    parser = argparse.ArgumentParser(
        description="Migracja danych z SQLite do PostgreSQL"
    )
    parser.add_argument(
        "--sqlite",
        default="sqlite:///./data/cennik.db",
        help="SQLite connection string (domyślnie: sqlite:///./data/cennik.db)",
    )
    parser.add_argument(
        "--postgres",
        default="postgresql://cennik_user:silne_haslo_123@172.16.10.201:2665/cennik_stali",
        help="PostgreSQL connection string",
    )
    parser.add_argument(
        "--tables",
        nargs="+",
        help="Nazwy tabel do migracji (domyślnie: wszystkie)",
    )
    parser.add_argument(
        "--skip-errors",
        action="store_true",
        help="Kontynuuj mimo błędów w pojedynczych tabelach",
    )

    args = parser.parse_args()

    try:
        migrate(
            sqlite_url=args.sqlite,
            postgres_url=args.postgres,
            tables=args.tables,
            skip_existing=args.skip_errors,
        )
    except Exception as e:
        print(f"\n[BŁĄD KRYTYCZNY] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
