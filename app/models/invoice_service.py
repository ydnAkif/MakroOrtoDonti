"""Invoice number generation and management utilities."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import select

from .models import ExchangeRate, Invoice, InvoiceItem, PatientTreatment, Settings, Treatment
from .database import get_session


class InvoiceService:

    @staticmethod
    def generate_invoice_number(session) -> str:
        prefix = (
            session.execute(
                select(Settings.value).where(Settings.key == "invoice_prefix")
            ).scalar_one_or_none()
            or "MKR"
        )
        next_num_str = (
            session.execute(
                select(Settings.value).where(Settings.key == "invoice_next_number")
            ).scalar_one_or_none()
            or "1"
        )
        next_num = int(next_num_str)
        year = date.today().year
        invoice_number = f"{prefix}-{year}-{next_num:04d}"

        settings_row = session.execute(
            select(Settings).where(Settings.key == "invoice_next_number")
        ).scalar_one()
        settings_row.value = str(next_num + 1)
        session.flush()

        return invoice_number

    @staticmethod
    def get_exchange_rate(session, target_date: Optional[date] = None) -> float:
        target_date = target_date or date.today()
        rate = session.execute(
            select(ExchangeRate)
            .where(ExchangeRate.rate_date <= target_date)
            .order_by(ExchangeRate.rate_date.desc())
            .limit(1)
        ).scalar_one_or_none()
        if rate is None:
            raise ValueError(
                f"No exchange rate found for date {target_date}. "
                "Please add an exchange rate first."
            )
        return rate.eur_to_try

    @staticmethod
    def create_invoice(
        session,
        patient_id: int,
        treatment_ids: list[int],
        invoice_date: Optional[date] = None,
        due_date: Optional[date] = None,
        notes: Optional[str] = None,
    ) -> Invoice:
        invoice_date = invoice_date or date.today()
        rate = InvoiceService.get_exchange_rate(session, invoice_date)
        invoice_number = InvoiceService.generate_invoice_number(session)

        invoice = Invoice(
            patient_id=patient_id,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            due_date=due_date,
            exchange_rate=rate,
            notes=notes,
        )
        session.add(invoice)
        session.flush()

        for tid in treatment_ids:
            pt = session.get(PatientTreatment, tid)
            if pt is None:
                raise ValueError(f"PatientTreatment {tid} not found")
            treatment = pt.treatment
            unit_eur = pt.effective_price_eur
            unit_try = round(unit_eur * rate, 2)

            item = InvoiceItem(
                invoice_id=invoice.id,
                treatment_id=treatment.id,
                description=treatment.name,
                quantity=1,
                unit_price_eur=unit_eur,
                unit_price_try=unit_try,
            )
            session.add(item)

        session.flush()
        invoice.recalculate_totals()
        session.commit()

        return invoice
