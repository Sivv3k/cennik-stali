"""Serwis do zbiorczych operacji na cenach."""

import json
from datetime import datetime
from typing import Optional
from math import ceil

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ..models.price import BasePrice, PriceChangeAudit
from ..models.material import Material, MaterialGroup, MaterialCategory
from ..models.user import User
from ..schemas.admin import (
    BulkPriceFilterRequest,
    BulkPricePreviewItem,
    BulkPricePreviewResponse,
    BulkPriceChangeResponse,
    BulkFilterOptionsResponse,
)


class BulkPricingService:
    """Serwis do zbiorczych zmian cen z filtrami."""

    def __init__(self, db: Session):
        self.db = db

    def build_filter_query(self, filters: BulkPriceFilterRequest):
        """Buduje zapytanie SQL z zastosowanymi filtrami."""
        query = (
            self.db.query(BasePrice)
            .join(Material, BasePrice.material_id == Material.id)
            .outerjoin(MaterialGroup, Material.group_id == MaterialGroup.id)
            .filter(BasePrice.is_active == True)
            .filter(BasePrice.price_pln_per_kg > 0)  # Pomijaj zablokowane (cena = 0)
        )

        # Filtr kategorii (multi-select)
        if filters.categories:
            category_enums = []
            for cat in filters.categories:
                try:
                    category_enums.append(MaterialCategory(cat))
                except ValueError:
                    pass
            if category_enums:
                query = query.filter(Material.category.in_(category_enums))

        # Filtr grup materiałów (multi-select)
        if filters.group_ids:
            query = query.filter(Material.group_id.in_(filters.group_ids))

        # Filtr gatunków (multi-select)
        if filters.grades:
            query = query.filter(Material.grade.in_(filters.grades))

        # Filtr wykończeń (multi-select)
        if filters.surface_finishes:
            query = query.filter(BasePrice.surface_finish.in_(filters.surface_finishes))

        # Filtr grubości
        if filters.thickness_min is not None:
            query = query.filter(BasePrice.thickness >= filters.thickness_min)
        if filters.thickness_max is not None:
            query = query.filter(BasePrice.thickness <= filters.thickness_max)

        # Filtr szerokości (multi-select przyciski)
        if filters.widths:
            query = query.filter(BasePrice.width.in_(filters.widths))

        return query

    def calculate_new_price(
        self,
        current_price: float,
        change_type: str,
        change_value: float,
        round_to: int = 2
    ) -> float:
        """Oblicza nową cenę na podstawie typu i wartości zmiany."""
        if change_type == "percentage":
            new_price = current_price * (1 + change_value / 100)
        else:  # absolute
            new_price = current_price + change_value

        # Nie pozwól na ujemne ceny
        new_price = max(0, new_price)

        return round(new_price, round_to)

    def preview_changes(
        self,
        filters: BulkPriceFilterRequest,
        change_type: str,
        change_value: float,
        page: int = 1,
        per_page: int = 50,
        round_to: int = 2
    ) -> BulkPricePreviewResponse:
        """Generuje podgląd zmian bez zapisywania."""
        query = self.build_filter_query(filters)

        # Dodaj eager loading dla materiału i grupy
        query = query.options(
            joinedload(BasePrice.material).joinedload(Material.group)
        )

        # Pobierz wszystkie pasujące ceny
        all_prices = query.all()
        total_affected = len(all_prices)

        # Oblicz sumy
        total_current = sum(p.price_pln_per_kg for p in all_prices)
        total_new = sum(
            self.calculate_new_price(p.price_pln_per_kg, change_type, change_value, round_to)
            for p in all_prices
        )

        # Paginacja
        total_pages = max(1, ceil(total_affected / per_page))
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_prices = all_prices[start_idx:end_idx]

        # Buduj elementy podglądu
        items = []
        for price in page_prices:
            new_price = self.calculate_new_price(
                price.price_pln_per_kg, change_type, change_value, round_to
            )
            items.append(BulkPricePreviewItem(
                id=price.id,
                material_grade=price.material.grade,
                material_name=price.material.name,
                group_name=price.material.group.name if price.material.group else None,
                surface_finish=price.surface_finish,
                thickness=price.thickness,
                width=price.width,
                current_price=price.price_pln_per_kg,
                new_price=new_price,
                change_amount=round(new_price - price.price_pln_per_kg, round_to)
            ))

        return BulkPricePreviewResponse(
            total_affected=total_affected,
            total_current_value=round(total_current, 2),
            total_new_value=round(total_new, 2),
            change_type=change_type,
            change_value=change_value,
            items=items,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )

    def apply_changes(
        self,
        filters: BulkPriceFilterRequest,
        change_type: str,
        change_value: float,
        user: User,
        round_to: int = 2,
        notes: Optional[str] = None
    ) -> BulkPriceChangeResponse:
        """Aplikuje zmiany cen i tworzy wpis audytu."""
        query = self.build_filter_query(filters)
        prices = query.all()

        updated_count = 0
        skipped_count = 0
        total_previous = 0.0
        total_new = 0.0

        for price in prices:
            old_price = price.price_pln_per_kg
            new_price = self.calculate_new_price(old_price, change_type, change_value, round_to)

            if new_price != old_price:
                total_previous += old_price
                total_new += new_price
                price.price_pln_per_kg = new_price
                updated_count += 1
            else:
                skipped_count += 1

        # Utwórz wpis audytu
        audit_entry = PriceChangeAudit(
            change_type=f"bulk_{change_type}",
            filters_json=json.dumps(filters.model_dump(), ensure_ascii=False),
            change_value=change_value,
            affected_count=updated_count,
            previous_total=round(total_previous, 2),
            new_total=round(total_new, 2),
            user_id=user.id,
            notes=notes
        )
        self.db.add(audit_entry)
        self.db.commit()

        return BulkPriceChangeResponse(
            success=True,
            updated_count=updated_count,
            skipped_count=skipped_count,
            total_previous=round(total_previous, 2),
            total_new=round(total_new, 2),
            change_type=change_type,
            change_value=change_value
        )

    def get_filter_options(
        self,
        categories: Optional[list[str]] = None,
        group_ids: Optional[list[int]] = None,
        grades: Optional[list[str]] = None,
        surface_finishes: Optional[list[str]] = None,
        widths: Optional[list[float]] = None
    ) -> BulkFilterOptionsResponse:
        """Zwraca dostępne opcje dla filtrów - dwukierunkowe filtrowanie.

        Każdy filtr wpływa na wszystkie pozostałe listy.
        """
        # Konwertuj kategorie na enumy
        category_enums = []
        if categories:
            for cat in categories:
                try:
                    category_enums.append(MaterialCategory(cat))
                except ValueError:
                    pass

        # Bazowe zapytanie dla cen (wspólne filtry)
        def base_price_query():
            return (
                self.db.query(BasePrice)
                .join(Material, BasePrice.material_id == Material.id)
                .outerjoin(MaterialGroup, Material.group_id == MaterialGroup.id)
                .filter(BasePrice.is_active == True)
                .filter(BasePrice.price_pln_per_kg > 0)
            )

        # Aplikuj filtry do zapytania
        def apply_filters(query, skip_filter=None):
            if category_enums and skip_filter != 'categories':
                query = query.filter(Material.category.in_(category_enums))
            if group_ids and skip_filter != 'groups':
                query = query.filter(Material.group_id.in_(group_ids))
            if grades and skip_filter != 'grades':
                query = query.filter(Material.grade.in_(grades))
            if surface_finishes and skip_filter != 'surface_finishes':
                query = query.filter(BasePrice.surface_finish.in_(surface_finishes))
            if widths and skip_filter != 'widths':
                query = query.filter(BasePrice.width.in_(widths))
            return query

        # === Kategorie - filtrowane przez pozostałe wybory ===
        cat_query = apply_filters(base_price_query(), skip_filter='categories')
        available_categories = set(
            m.category for m in
            self.db.query(Material.category)
            .filter(Material.id.in_(cat_query.with_entities(BasePrice.material_id).distinct()))
            .distinct().all()
        )
        categories_list = [
            {"value": c.value, "label": c.name}
            for c in MaterialCategory
            if not (categories or group_ids or grades or surface_finishes or widths) or c in available_categories
        ]

        # === Grupy - filtrowane przez pozostałe wybory ===
        groups_query = apply_filters(base_price_query(), skip_filter='groups')
        available_group_ids = set(
            m.group_id for m in
            self.db.query(Material.group_id)
            .filter(Material.id.in_(groups_query.with_entities(BasePrice.material_id).distinct()))
            .filter(Material.group_id.isnot(None))
            .distinct().all()
        )
        all_groups = (
            self.db.query(MaterialGroup)
            .filter(MaterialGroup.is_active == True)
            .order_by(MaterialGroup.display_order)
            .all()
        )
        groups = [
            {"id": g.id, "name": g.name, "category": g.category.value}
            for g in all_groups
            if not (categories or group_ids or grades or surface_finishes or widths) or g.id in available_group_ids
        ]

        # === Gatunki - filtrowane przez pozostałe wybory ===
        grades_subquery = apply_filters(base_price_query(), skip_filter='grades')
        available_grades_set = set(
            m.grade for m in
            self.db.query(Material.grade)
            .filter(Material.id.in_(grades_subquery.with_entities(BasePrice.material_id).distinct()))
            .distinct().all()
        )
        available_grades = sorted(list(available_grades_set))

        # === Wykończenia - filtrowane przez pozostałe wybory ===
        finishes_query = apply_filters(base_price_query(), skip_filter='surface_finishes')
        available_finishes = sorted([
            f[0] for f in finishes_query.with_entities(BasePrice.surface_finish).distinct().all()
        ])

        # === Szerokości - filtrowane przez pozostałe wybory ===
        widths_query = apply_filters(base_price_query(), skip_filter='widths')
        available_widths = sorted([
            w[0] for w in widths_query.with_entities(BasePrice.width).distinct().all()
        ])

        # === Zakres grubości - filtrowane przez wszystkie wybory ===
        thickness_query = apply_filters(base_price_query())
        thickness_stats = thickness_query.with_entities(
            func.min(BasePrice.thickness),
            func.max(BasePrice.thickness)
        ).first()
        thickness_range = {
            "min": thickness_stats[0] or 0,
            "max": thickness_stats[1] or 0
        }

        return BulkFilterOptionsResponse(
            categories=categories_list,
            groups=groups,
            grades=available_grades,
            surface_finishes=available_finishes,
            thickness_range=thickness_range,
            widths=available_widths
        )

    def get_audit_history(
        self,
        limit: int = 50,
        offset: int = 0,
        change_type: Optional[str] = None
    ) -> list[dict]:
        """Pobiera historię zmian cen."""
        query = (
            self.db.query(PriceChangeAudit)
            .options(joinedload(PriceChangeAudit.user))
            .order_by(PriceChangeAudit.created_at.desc())
        )

        if change_type:
            query = query.filter(PriceChangeAudit.change_type == change_type)

        audits = query.offset(offset).limit(limit).all()

        return [
            {
                "id": a.id,
                "change_type": a.change_type,
                "change_value": a.change_value,
                "affected_count": a.affected_count,
                "previous_total": a.previous_total,
                "new_total": a.new_total,
                "user": a.user.username if a.user else "unknown",
                "created_at": a.created_at.isoformat(),
                "filters": json.loads(a.filters_json) if a.filters_json else None,
                "notes": a.notes
            }
            for a in audits
        ]
