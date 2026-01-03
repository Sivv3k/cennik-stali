# CTL/Multiblanking Machine Pricing System - Design

## Overview

System kalkulacji cen z obsługą maszyn CTL (ATH, RBI) i Multiblankingu z automatyczną optymalizacją odpadu.

## Maszyny i limity

| Maszyna | Max grubość | Max szerokość | Możliwości |
|---------|-------------|---------------|------------|
| **RBI** | 3 mm | 1500 mm | CTL + Multiblanking |
| **ATH** | 12 mm | 2000 mm | tylko CTL |

### Logika wyboru maszyny

```python
if thickness <= 3 and width <= 1500:
    available = ["RBI", "ATH"]  # RBI domyślnie (tańszy dla cienkich)
    multiblanking_available = True
elif thickness <= 12 and width <= 2000:
    available = ["ATH"]
    multiblanking_available = False
else:
    error = "Brak dostępnej maszyny"
```

## Model danych

### Nowa tabela: `machine_prices`

```sql
CREATE TABLE machine_prices (
    id SERIAL PRIMARY KEY,
    machine_type VARCHAR(10) NOT NULL,  -- 'ATH', 'RBI'
    operation_type VARCHAR(20) NOT NULL, -- 'CTL', 'MULTIBLANKING'
    thickness FLOAT NOT NULL,
    surcharge_pln_per_kg FLOAT NOT NULL,
    thickness_max FLOAT NOT NULL,  -- limit maszyny
    width_max FLOAT NOT NULL,      -- limit maszyny
    is_active BOOLEAN DEFAULT TRUE,
    notes VARCHAR(200)
);
```

### Przykładowe dane

| Maszyna | Operacja | Grubość | Dopłata PLN/kg |
|---------|----------|---------|----------------|
| ATH | CTL | 0.5 | 0.35 |
| ATH | CTL | 1.0 | 0.30 |
| ATH | CTL | 2.0 | 0.25 |
| RBI | CTL | 0.5 | 0.40 |
| RBI | CTL | 1.0 | 0.35 |
| RBI | MULTIBLANKING | 0.5 | 0.90 |
| RBI | MULTIBLANKING | 1.0 | 0.80 |

## Kalkulacja Multiblankingu

### Optymalizacja szerokości źródłowej

Dostępne szerokości źródłowe: 1000, 1250, 1500 mm

Dla szerokości docelowej 220mm:

| Źródło | Sztuk | Odpad | Wykorzystanie |
|--------|-------|-------|---------------|
| 1000 mm | 4 szt | 120 mm | 88% |
| 1250 mm | 5 szt | 150 mm | 88% |
| 1500 mm | 6 szt | 180 mm | 88% |

System wybiera szerokość z najwyższym % wykorzystania.

### Wzór na cenę jednostkową

```python
cena_kg_total = cena_bazowa + szlif + folia + doplata_maszyny

waga_zrodlowa = (szer_zrodl/1000) * (dl/1000) * grub * 7.9
cena_arkusza_zrodl = waga_zrodlowa * cena_kg_total
cena_sztuki = cena_arkusza_zrodl / ilosc_sztuk_z_arkusza
```

## Filtry kaskadowe

### Endpoint API

```
GET /api/prices/filter-options/
    ?category=stal_nierdzewna
    &thickness=2
```

### Odpowiedź

```json
{
  "grades": ["1.4301", "1.4404", "1.4541"],
  "surfaces": ["2B", "BA", "No.4"],
  "thicknesses": [0.5, 1.0, 1.5, 2.0, 3.0],
  "widths": [1000, 1250, 1500],
  "machines": ["RBI", "ATH"]
}
```

### Kolejność filtrów

1. Kategoria
2. Gatunek (dynamiczny)
3. Powierzchnia (dynamiczna)
4. Grubość (dynamiczna)
5. Maszyna (ATH/RBI - ograniczona przez grubość/szerokość)
6. Typ operacji (CTL / Multiblanking)
7. Wymiary docelowe (szerokość × długość)
8. Szlif (provider + granulacja + 2x)
9. Folia (typ + 2x)
10. Ilość arkuszy

## Zmiany UI

### Panel filtrów

- Szerokość: 288px (`w-72`)
- Kompaktowe inputy: `py-1.5 text-sm`
- Sekcje zwijane dla szlifu/folii

### Tabela wyników

| Kolumna | Zawartość | Przykład |
|---------|-----------|----------|
| Gatunek | grade + surface | "1.4301 2B" |
| Wymiar | grubość × szer × dł | "1.5 × 1000 × 2000" |
| Obróbka | badges | CTL/RBI, Szlif, Folia |
| Ilość | input number | 1 |
| PLN/kg | cena za kg | 15.50 |
| PLN/szt | cena arkusza | 245.70 |
| PLN/razem | szt × ilość | **491.40** |

### Sekcja podsumowania

```
Optymalizacja: źródło 1000mm → 4 szt/arkusz (88% wykorzystania)
Odpad: 120mm wliczony w cenę
```

## Pliki do modyfikacji/utworzenia

### Nowe pliki

- `src/models/machine.py` - model MachinePrice
- `src/schemas/machine.py` - schematy Pydantic
- `src/services/calculator.py` - logika kalkulacji
- `src/templates/admin/machines.html` - panel zarządzania maszynami

### Modyfikacje

- `src/routers/prices.py` - nowe endpointy, logika filtrów
- `src/templates/index.html` - nowy formularz, węższa kolumna
- `src/templates/price_table.html` - nowa struktura tabeli
- `src/models/__init__.py` - eksport MachinePrice
- `src/main.py` - nowa strona /admin/machines

## Fazy implementacji

### Faza 1: Model danych i backend
- Utworzenie modelu MachinePrice
- Migracja bazy danych
- Endpoint filter-options
- Logika kalkulacji multiblankingu

### Faza 2: UI kalkulatora
- Nowa struktura tabeli wyników
- Węższy panel filtrów
- Filtry kaskadowe (HTMX)
- Input ilości z przeliczaniem

### Faza 3: Panel admina
- Strona /admin/machines
- CRUD dla dopłat maszynowych
- Import z Excel

---

*Dokument utworzony: 2026-01-03*
