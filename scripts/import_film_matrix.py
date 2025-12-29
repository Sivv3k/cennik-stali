"""Import danych folii z Excela do bazy danych."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from src.database import SessionLocal, init_db
from src.models import FilmPrice, FilmType

# Standard thicknesses
STANDARD_THICKNESSES = [
    0.4, 0.5, 0.6, 0.7, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0
]

def import_film_data():
    """Import film prices from Excel."""

    init_db()
    db = SessionLocal()

    # Read Excel
    xl = pd.ExcelFile('data/imports/Kopia CENNIK NOWY.xlsx')
    df = pd.read_excel(xl, sheet_name='DANE FOLIA', header=None)

    # Clear existing data
    db.query(FilmPrice).delete()
    db.commit()
    print("Wyczyszczono istniejace dane folii")

    # Film data from Excel (row 3 onwards, column 0 = thickness)
    film_data = {}

    # Parse data from Excel
    for idx in range(3, 25):
        row = df.iloc[idx]
        thickness = row.iloc[0]

        if pd.isna(thickness):
            continue

        thickness = float(thickness)
        film_data[thickness] = {
            FilmType.NOVACEL_4228: row.iloc[1] if pd.notna(row.iloc[1]) else 0,
            FilmType.FOLIA_FIBER: row.iloc[2] if pd.notna(row.iloc[2]) else 0,
            FilmType.FOLIA_ZWYKLA: row.iloc[3] if pd.notna(row.iloc[3]) else 0,
            FilmType.NITTO_3100: row.iloc[4] if pd.notna(row.iloc[4]) else 0,
            FilmType.NITTO_3067M: row.iloc[5] if pd.notna(row.iloc[5]) else 0,
            FilmType.NITTO_AFP585: row.iloc[6] if pd.notna(row.iloc[6]) else 0,
            FilmType.NITTO_224PR: row.iloc[7] if pd.notna(row.iloc[7]) else 0,
        }

    count = 0

    # Import for all standard thicknesses
    for thickness in STANDARD_THICKNESSES:
        for film_type in FilmType:
            if thickness in film_data and film_type in film_data[thickness]:
                price = float(film_data[thickness][film_type])
            else:
                price = 0  # Brak danych = 0

            fp = FilmPrice(
                film_type=film_type,
                thickness=thickness,
                price_pln_per_kg=round(price, 4),
            )
            db.add(fp)
            count += 1

    db.commit()
    print(f"\n=== SUKCES: Zaimportowano {count} wpisow folii ===")

    # Statystyki
    print("\nStatystyki:")
    for film_type in FilmType:
        total = db.query(FilmPrice).filter(FilmPrice.film_type == film_type).count()
        available = db.query(FilmPrice).filter(
            FilmPrice.film_type == film_type,
            FilmPrice.price_pln_per_kg > 0
        ).count()
        blocked = total - available
        print(f"  {film_type.value}: {total} wpisow ({available} dostepnych, {blocked} zablokowanych)")

    db.close()


if __name__ == "__main__":
    import_film_data()
