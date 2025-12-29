#!/usr/bin/env python3
"""Seed database with steel grades data."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import SessionLocal
from src.models import Material, MaterialGroup, MaterialCategory


# === GRUPY MATERIAŁÓW ===

GROUPS = [
    # Stal nierdzewna
    {
        "name": "Austenityczne",
        "category": MaterialCategory.STAINLESS_STEEL,
        "description": "Stale chromowo-niklowe, niemagnetyczne, o wysokiej odporności na korozję. Najczęściej stosowane stale nierdzewne.",
        "display_order": 1,
    },
    {
        "name": "Ferrytyczne",
        "category": MaterialCategory.STAINLESS_STEEL,
        "description": "Stale chromowe, magnetyczne, tańsze od austenitycznych. Dobra odporność na korozję naprężeniową.",
        "display_order": 2,
    },
    {
        "name": "Martenzytyczne",
        "category": MaterialCategory.STAINLESS_STEEL,
        "description": "Stale chromowe hartowalne, magnetyczne. Wysoka twardość i wytrzymałość.",
        "display_order": 3,
    },
    {
        "name": "Duplex",
        "category": MaterialCategory.STAINLESS_STEEL,
        "description": "Stale austenityczno-ferrytyczne o podwyższonej wytrzymałości i odporności na korozję.",
        "display_order": 4,
    },
    # Stal czarna
    {
        "name": "Stale konstrukcyjne",
        "category": MaterialCategory.CARBON_STEEL,
        "description": "Stale do zastosowań konstrukcyjnych ogólnego przeznaczenia.",
        "display_order": 1,
    },
    {
        "name": "Stale głębokotłoczne",
        "category": MaterialCategory.CARBON_STEEL,
        "description": "Stale do tłoczenia i formowania na zimno.",
        "display_order": 2,
    },
    {
        "name": "Stale kotłowe",
        "category": MaterialCategory.CARBON_STEEL,
        "description": "Stale do pracy w podwyższonych temperaturach.",
        "display_order": 3,
    },
    # Aluminium
    {
        "name": "Seria 1xxx - Aluminium czyste",
        "category": MaterialCategory.ALUMINUM,
        "description": "Aluminium techniczne o czystości min. 99%. Doskonała odporność na korozję i przewodność.",
        "display_order": 1,
    },
    {
        "name": "Seria 3xxx - Al-Mn",
        "category": MaterialCategory.ALUMINUM,
        "description": "Stopy aluminium z manganem. Dobra formowalność i odporność na korozję.",
        "display_order": 2,
    },
    {
        "name": "Seria 5xxx - Al-Mg",
        "category": MaterialCategory.ALUMINUM,
        "description": "Stopy aluminium z magnezem. Wysoka wytrzymałość i odporność na korozję morską.",
        "display_order": 3,
    },
    {
        "name": "Seria 6xxx - Al-Mg-Si",
        "category": MaterialCategory.ALUMINUM,
        "description": "Stopy utwardzane wydzieleniowo. Dobra wytrzymałość i spawalność.",
        "display_order": 4,
    },
]


# === GATUNKI STALI NIERDZEWNEJ ===

STAINLESS_STEEL = [
    # Austenityczne
    {
        "name": "1.4301 (AISI 304)",
        "grade": "1.4301",
        "group_name": "Austenityczne",
        "standard": "EN 10088-2",
        "equivalent_grades": "AISI 304, X5CrNi18-10, SUS 304",
        "composition": "C≤0.07, Cr 17.5-19.5, Ni 8-10.5",
        "density": 7.9,
        "tensile_strength": "500-700 MPa",
        "yield_strength": "≥190 MPa",
        "applications": "Przemysł spożywczy, chemiczny, architektura, wyposażenie kuchni",
        "description": "Najpopularniejsza stal nierdzewna. Doskonała odporność na korozję, dobra spawalność.",
        "display_order": 1,
    },
    {
        "name": "1.4307 (AISI 304L)",
        "grade": "1.4307",
        "group_name": "Austenityczne",
        "standard": "EN 10088-2",
        "equivalent_grades": "AISI 304L, X2CrNi18-9",
        "composition": "C≤0.03, Cr 17.5-19.5, Ni 8-10.5",
        "density": 7.9,
        "tensile_strength": "500-700 MPa",
        "yield_strength": "≥175 MPa",
        "applications": "Konstrukcje spawane, przemysł chemiczny",
        "description": "Wersja niskowęglowa 304. Lepsza spawalność, odporna na korozję międzykrystaliczną.",
        "display_order": 2,
    },
    {
        "name": "1.4404 (AISI 316L)",
        "grade": "1.4404",
        "group_name": "Austenityczne",
        "standard": "EN 10088-2",
        "equivalent_grades": "AISI 316L, X2CrNiMo17-12-2",
        "composition": "C≤0.03, Cr 16.5-18.5, Ni 10-13, Mo 2-2.5",
        "density": 8.0,
        "tensile_strength": "500-700 MPa",
        "yield_strength": "≥200 MPa",
        "applications": "Przemysł chemiczny, farmaceutyczny, morski, medyczny",
        "description": "Stal kwasoodporna z molibdenem. Lepsza odporność na korozję wżerową.",
        "display_order": 3,
    },
    {
        "name": "1.4401 (AISI 316)",
        "grade": "1.4401",
        "group_name": "Austenityczne",
        "standard": "EN 10088-2",
        "equivalent_grades": "AISI 316, X5CrNiMo17-12-2",
        "composition": "C≤0.07, Cr 16.5-18.5, Ni 10-13, Mo 2-2.5",
        "density": 8.0,
        "tensile_strength": "500-700 MPa",
        "yield_strength": "≥200 MPa",
        "applications": "Przemysł chemiczny, morski",
        "description": "Stal z molibdenem. Wysoka odporność na chlorki.",
        "display_order": 4,
    },
    {
        "name": "1.4541 (AISI 321)",
        "grade": "1.4541",
        "group_name": "Austenityczne",
        "standard": "EN 10088-2",
        "equivalent_grades": "AISI 321, X6CrNiTi18-10",
        "composition": "C≤0.08, Cr 17-19, Ni 9-12, Ti 5xC-0.7",
        "density": 7.9,
        "tensile_strength": "500-720 MPa",
        "yield_strength": "≥190 MPa",
        "applications": "Przemysł lotniczy, spaliny, wysokie temperatury",
        "description": "Stal stabilizowana tytanem. Odporna na korozję międzykrystaliczną w wysokich temp.",
        "display_order": 5,
    },
    # Ferrytyczne
    {
        "name": "1.4016 (AISI 430)",
        "grade": "1.4016",
        "group_name": "Ferrytyczne",
        "standard": "EN 10088-2",
        "equivalent_grades": "AISI 430, X6Cr17",
        "composition": "C≤0.08, Cr 16-18",
        "density": 7.7,
        "tensile_strength": "450-600 MPa",
        "yield_strength": "≥260 MPa",
        "applications": "AGD, elementy dekoracyjne, obudowy",
        "description": "Podstawowa stal ferrytyczna. Magnetyczna, tańsza od austenitycznych.",
        "display_order": 1,
    },
    {
        "name": "1.4512 (AISI 409)",
        "grade": "1.4512",
        "group_name": "Ferrytyczne",
        "standard": "EN 10088-2",
        "equivalent_grades": "AISI 409, X2CrTi12",
        "composition": "C≤0.03, Cr 10.5-12.5, Ti 6xC-0.65",
        "density": 7.7,
        "tensile_strength": "380-560 MPa",
        "yield_strength": "≥210 MPa",
        "applications": "Układy wydechowe, spawane konstrukcje",
        "description": "Stal stabilizowana tytanem. Dobra spawalność.",
        "display_order": 2,
    },
    # Martenzytyczne
    {
        "name": "1.4021 (AISI 420)",
        "grade": "1.4021",
        "group_name": "Martenzytyczne",
        "standard": "EN 10088-2",
        "equivalent_grades": "AISI 420, X20Cr13",
        "composition": "C 0.16-0.25, Cr 12-14",
        "density": 7.7,
        "tensile_strength": "700-850 MPa",
        "yield_strength": "≥500 MPa",
        "applications": "Noże, narzędzia chirurgiczne, sprężyny",
        "description": "Stal hartowalna. Wysoka twardość po obróbce cieplnej.",
        "display_order": 1,
    },
    # Duplex
    {
        "name": "1.4462 (SAF 2205)",
        "grade": "1.4462",
        "group_name": "Duplex",
        "standard": "EN 10088-2",
        "equivalent_grades": "SAF 2205, X2CrNiMoN22-5-3",
        "composition": "C≤0.03, Cr 21-23, Ni 4.5-6.5, Mo 2.5-3.5, N 0.1-0.22",
        "density": 7.8,
        "tensile_strength": "640-880 MPa",
        "yield_strength": "≥450 MPa",
        "applications": "Przemysł petrochemiczny, morski, papierniczy",
        "description": "Stal duplex. Podwójna wytrzymałość austenitycznych, lepsza odporność na korozję.",
        "display_order": 1,
    },
]


# === GATUNKI STALI CZARNEJ ===

CARBON_STEEL = [
    # Konstrukcyjne
    {
        "name": "S235JR",
        "grade": "S235JR",
        "group_name": "Stale konstrukcyjne",
        "standard": "EN 10025-2",
        "equivalent_grades": "St37-2, RSt37-2",
        "composition": "C≤0.17, Mn≤1.40, P≤0.035, S≤0.035",
        "density": 7.85,
        "tensile_strength": "360-510 MPa",
        "yield_strength": "≥235 MPa",
        "applications": "Konstrukcje stalowe, mosty, budynki",
        "description": "Podstawowa stal konstrukcyjna. Szeroko stosowana w budownictwie.",
        "display_order": 1,
    },
    {
        "name": "S355JR",
        "grade": "S355JR",
        "group_name": "Stale konstrukcyjne",
        "standard": "EN 10025-2",
        "equivalent_grades": "St52-3, E355",
        "composition": "C≤0.24, Mn≤1.60, P≤0.035, S≤0.035",
        "density": 7.85,
        "tensile_strength": "470-630 MPa",
        "yield_strength": "≥355 MPa",
        "applications": "Konstrukcje ciężkie, maszyny, pojazdy",
        "description": "Stal konstrukcyjna o podwyższonej wytrzymałości.",
        "display_order": 2,
    },
    {
        "name": "S355J2",
        "grade": "S355J2",
        "group_name": "Stale konstrukcyjne",
        "standard": "EN 10025-2",
        "equivalent_grades": "E355",
        "composition": "C≤0.22, Mn≤1.60",
        "density": 7.85,
        "tensile_strength": "470-630 MPa",
        "yield_strength": "≥355 MPa",
        "applications": "Konstrukcje pracujące w niskich temperaturach",
        "description": "Stal S355 z gwarantowaną udarnością w -20°C.",
        "display_order": 3,
    },
    # Głębokotłoczne
    {
        "name": "DC01",
        "grade": "DC01",
        "group_name": "Stale głębokotłoczne",
        "standard": "EN 10130",
        "equivalent_grades": "St12, SPCC",
        "composition": "C≤0.12, Mn≤0.60",
        "density": 7.85,
        "tensile_strength": "270-410 MPa",
        "yield_strength": "140-280 MPa",
        "applications": "Obudowy, panele, proste tłoczenie",
        "description": "Podstawowa stal do tłoczenia na zimno.",
        "display_order": 1,
    },
    {
        "name": "DC03",
        "grade": "DC03",
        "group_name": "Stale głębokotłoczne",
        "standard": "EN 10130",
        "equivalent_grades": "St13, SPCD",
        "composition": "C≤0.10, Mn≤0.45",
        "density": 7.85,
        "tensile_strength": "270-370 MPa",
        "yield_strength": "140-240 MPa",
        "applications": "Tłoczenie średnio głębokie",
        "description": "Stal do tłoczenia o lepszej ciągliwości niż DC01.",
        "display_order": 2,
    },
    {
        "name": "DC04",
        "grade": "DC04",
        "group_name": "Stale głębokotłoczne",
        "standard": "EN 10130",
        "equivalent_grades": "St14, SPCE",
        "composition": "C≤0.08, Mn≤0.40",
        "density": 7.85,
        "tensile_strength": "270-350 MPa",
        "yield_strength": "140-210 MPa",
        "applications": "Głębokie tłoczenie, elementy karoserii",
        "description": "Stal do głębokiego tłoczenia. Wysoka plastyczność.",
        "display_order": 3,
    },
    {
        "name": "DC05",
        "grade": "DC05",
        "group_name": "Stale głębokotłoczne",
        "standard": "EN 10130",
        "equivalent_grades": "St15",
        "composition": "C≤0.06, Mn≤0.35",
        "density": 7.85,
        "tensile_strength": "270-330 MPa",
        "yield_strength": "140-180 MPa",
        "applications": "Bardzo głębokie tłoczenie",
        "description": "Najlepsza stal do bardzo głębokiego tłoczenia.",
        "display_order": 4,
    },
    # Kotłowe
    {
        "name": "P265GH",
        "grade": "P265GH",
        "group_name": "Stale kotłowe",
        "standard": "EN 10028-2",
        "equivalent_grades": "HII, 1.0425",
        "composition": "C≤0.20, Mn 0.80-1.40",
        "density": 7.85,
        "tensile_strength": "410-530 MPa",
        "yield_strength": "≥265 MPa",
        "applications": "Zbiorniki ciśnieniowe, kotły",
        "description": "Stal do pracy pod ciśnieniem w podwyższonych temperaturach.",
        "display_order": 1,
    },
]


# === GATUNKI ALUMINIUM ===

ALUMINUM = [
    # Seria 1xxx
    {
        "name": "EN AW-1050A",
        "grade": "1050A",
        "group_name": "Seria 1xxx - Aluminium czyste",
        "standard": "EN 573-3, EN 485-2",
        "equivalent_grades": "AA1050, Al99.5",
        "composition": "Al ≥99.50, Fe≤0.40, Si≤0.25",
        "density": 2.71,
        "tensile_strength": "65-95 MPa",
        "yield_strength": "≥20 MPa",
        "applications": "Reflektory, izolacje, przemysł chemiczny",
        "description": "Aluminium techniczne 99.5%. Doskonała odporność na korozję i przewodność.",
        "display_order": 1,
    },
    # Seria 3xxx
    {
        "name": "EN AW-3003",
        "grade": "3003",
        "group_name": "Seria 3xxx - Al-Mn",
        "standard": "EN 573-3, EN 485-2",
        "equivalent_grades": "AA3003, AlMn1Cu",
        "composition": "Al bal., Mn 1.0-1.5, Cu 0.05-0.20",
        "density": 2.73,
        "tensile_strength": "95-130 MPa",
        "yield_strength": "≥35 MPa",
        "applications": "Naczynia kuchenne, wymienniki ciepła",
        "description": "Stop Al-Mn o dobrej formowalności i odporności na korozję.",
        "display_order": 1,
    },
    {
        "name": "EN AW-3105",
        "grade": "3105",
        "group_name": "Seria 3xxx - Al-Mn",
        "standard": "EN 573-3",
        "equivalent_grades": "AA3105, AlMn0.5Mg0.5",
        "composition": "Al bal., Mn 0.30-0.8, Mg 0.20-0.8",
        "density": 2.72,
        "tensile_strength": "115-145 MPa",
        "yield_strength": "≥75 MPa",
        "applications": "Pokrycia dachowe, rynny, obudowy",
        "description": "Stop Al-Mn-Mg. Lepsza wytrzymałość niż 3003.",
        "display_order": 2,
    },
    # Seria 5xxx
    {
        "name": "EN AW-5005",
        "grade": "5005",
        "group_name": "Seria 5xxx - Al-Mg",
        "standard": "EN 573-3, EN 485-2",
        "equivalent_grades": "AA5005, AlMg1",
        "composition": "Al bal., Mg 0.50-1.1",
        "density": 2.70,
        "tensile_strength": "100-145 MPa",
        "yield_strength": "≥35 MPa",
        "applications": "Architektura, elewacje, wyposażenie wnętrz",
        "description": "Stop Al-Mg o dobrej anodizowalności i odporności na korozję.",
        "display_order": 1,
    },
    {
        "name": "EN AW-5754",
        "grade": "5754",
        "group_name": "Seria 5xxx - Al-Mg",
        "standard": "EN 573-3, EN 485-2",
        "equivalent_grades": "AA5754, AlMg3",
        "composition": "Al bal., Mg 2.6-3.6, Mn 0.50",
        "density": 2.66,
        "tensile_strength": "190-240 MPa",
        "yield_strength": "≥80 MPa",
        "applications": "Przemysł morski, motoryzacyjny, zbiorniki",
        "description": "Stop Al-Mg o wysokiej odporności na korozję morską. Dobra spawalność.",
        "display_order": 2,
    },
    {
        "name": "EN AW-5083",
        "grade": "5083",
        "group_name": "Seria 5xxx - Al-Mg",
        "standard": "EN 573-3, EN 485-2",
        "equivalent_grades": "AA5083, AlMg4.5Mn0.7",
        "composition": "Al bal., Mg 4.0-4.9, Mn 0.40-1.0",
        "density": 2.66,
        "tensile_strength": "275-350 MPa",
        "yield_strength": "≥125 MPa",
        "applications": "Konstrukcje morskie, zbiorniki kriogeniczne, pojazdy",
        "description": "Najwytrzymalszy stop serii 5xxx. Doskonała odporność na korozję.",
        "display_order": 3,
    },
    # Seria 6xxx
    {
        "name": "EN AW-6060",
        "grade": "6060",
        "group_name": "Seria 6xxx - Al-Mg-Si",
        "standard": "EN 573-3, EN 755-2",
        "equivalent_grades": "AA6060, AlMgSi0.5",
        "composition": "Al bal., Mg 0.35-0.6, Si 0.30-0.6",
        "density": 2.70,
        "tensile_strength": "170-220 MPa",
        "yield_strength": "≥140 MPa",
        "applications": "Profile architektoniczne, ramy okienne",
        "description": "Stop do wyciskania. Bardzo dobra anodizowalność.",
        "display_order": 1,
    },
    {
        "name": "EN AW-6082",
        "grade": "6082",
        "group_name": "Seria 6xxx - Al-Mg-Si",
        "standard": "EN 573-3, EN 485-2",
        "equivalent_grades": "AA6082, AlSi1MgMn",
        "composition": "Al bal., Si 0.7-1.3, Mg 0.6-1.2, Mn 0.40-1.0",
        "density": 2.71,
        "tensile_strength": "290-340 MPa",
        "yield_strength": "≥250 MPa",
        "applications": "Konstrukcje, mosty, transport",
        "description": "Najwytrzymalszy stop serii 6xxx. Utwardzany wydzieleniowo.",
        "display_order": 2,
    },
]


def seed_materials():
    """Seed database with material groups and materials."""
    db = SessionLocal()

    try:
        # Utwórz grupy
        print("Tworzenie grup materiałów...")
        group_map = {}
        for group_data in GROUPS:
            existing = db.query(MaterialGroup).filter(MaterialGroup.name == group_data["name"]).first()
            if existing:
                group_map[group_data["name"]] = existing
                print(f"  Grupa '{group_data['name']}' już istnieje")
            else:
                group = MaterialGroup(**group_data)
                db.add(group)
                db.flush()
                group_map[group_data["name"]] = group
                print(f"  Utworzono grupę: {group_data['name']}")

        db.commit()

        # Utwórz materiały
        print("\nTworzenie gatunków materiałów...")

        all_materials = [
            *[(m, MaterialCategory.STAINLESS_STEEL) for m in STAINLESS_STEEL],
            *[(m, MaterialCategory.CARBON_STEEL) for m in CARBON_STEEL],
            *[(m, MaterialCategory.ALUMINUM) for m in ALUMINUM],
        ]

        created = 0
        skipped = 0
        for material_data, category in all_materials:
            existing = db.query(Material).filter(Material.grade == material_data["grade"]).first()
            if existing:
                skipped += 1
                continue

            group_name = material_data.pop("group_name")
            group = group_map.get(group_name)

            material = Material(
                **material_data,
                category=category,
                group_id=group.id if group else None,
            )
            db.add(material)
            created += 1
            print(f"  Utworzono: {material_data['name']}")

        db.commit()

        print(f"\nGotowe! Utworzono {created} gatunków, pominięto {skipped} istniejących.")

    except Exception as e:
        print(f"BŁĄD: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_materials()
