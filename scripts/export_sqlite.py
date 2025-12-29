#!/usr/bin/env python3
"""Eksport danych z SQLite do JSON."""

import json
import sqlite3
from pathlib import Path


def export_sqlite_data(db_path: str = "cennik.db", output_path: str = "data_export.json"):
    """Eksportuj wszystkie dane z SQLite do JSON."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Pobierz listę tabel
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version'"
    )
    tables = [row[0] for row in cursor.fetchall()]

    print(f"Znaleziono {len(tables)} tabel: {tables}")

    data = {}
    for table in tables:
        cursor = conn.execute(f"SELECT * FROM {table}")
        rows = cursor.fetchall()
        data[table] = [dict(row) for row in rows]
        print(f"  {table}: {len(data[table])} rekordów")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    print(f"\nEksportowano do: {output_path}")
    conn.close()


if __name__ == "__main__":
    export_sqlite_data()
