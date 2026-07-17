from __future__ import annotations

from datetime import date, datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from flask_login import UserMixin
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Enum as SQLEnum,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from .patient import Patient
    from .invoice import Invoice, InvoiceItem


class TreatmentCategory:
    ORTHODONTIC = "orthodontic"
    PROSTHETIC = "prosthetic"
    SURGICAL = "surgical"
    PREVENTIVE = "preventive"
    RESTORATIVE = "restorative"
    ENDODONTIC = "periodontic"
    IMPLANT = "implant"
    COSMETIC = "cosmetic"
    OTHER = "other"

    ALL = [
        ORTHODONTIC,
        PROSTHETIC,
        SURGICAL,
        PREVENTIVE,
        RESTORATIVE,
        ENDODONTIC,
        IMPLANT,
        COSMETIC,
        OTHER,
    ]


class PartyType(PyEnum):
    PATIENT = "patient"
    DENTIST_CUSTOMER = "dentist_customer"
    COMPANY_CUSTOMER = "company_customer"


class InvoiceItemType(PyEnum):
    TREATMENT = "treatment"
    PRODUCT = "product"
    SERVICE = "service"
    LAB = "lab"
    CUSTOM = "custom"


class Party(Base, TimestampMixin):
    """Unified entity for all parties: patients, dentist customers, company customers."""
    __tablename__ = "parties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    party_type: Mapped[str] = mapped_column(
        SQLEnum(PartyType), nullable=False, default=PartyType.PATIENT, index=True
    )
    # Common fields
    name: Mapped[str] = mapped_column(String(200), nullable=False)  # full name or company name
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(50), nullable=True)  # TC Kimlik / Vergi No
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Patient-specific fields (used when party_type = PATIENT)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(nullable=True)
    treatment_status: Mapped[str] = mapped_column(
        String(30), default="active", nullable=False, index=True
    )

    # Company-specific fields (used when party_type = COMPANY_CUSTOMER)
    contact_person: Mapped[str | None] = mapped_column(String(150), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Doctor link (patients -> referring dentist)
    referred_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("parties.id"), nullable=True, index=True)
    referred_by = relationship("Party", remote_side="Party.id", foreign_keys=[referred_by_id], lazy="selectin")

    # Relationships
    invoices: Mapped[list["Invoice"]] = relationship(
        back_populates="party", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("name", "phone", "party_type", name="uq_party_identity"),
    )

    @property
    def display_name(self) -> str:
        if self.party_type == PartyType.PATIENT:
            return f"{self.first_name or ''} {self.last_name or ''}".strip() or self.name
        return self.name

    @property
    def is_patient(self) -> bool:
        return self.party_type == PartyType.PATIENT

    def __repr__(self) -> str:
        return f"<Party {self.display_name} ({self.party_type.value})>"


class Treatment(Base, TimestampMixin):
    __tablename__ = "treatments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, default=TreatmentCategory.OTHER
    )
    price_eur: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    patient_treatments: Mapped[list["PatientTreatment"]] = relationship(
        back_populates="treatment", lazy="selectin"
    )
    invoice_items: Mapped[list["InvoiceItem"]] = relationship(
        back_populates="treatment", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("name", name="uq_treatment_name"),
    )

    def __repr__(self) -> str:
        return f"<Treatment {self.name} €{self.price_eur:.2f}>"


class Patient(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    treatment_status: Mapped[str] = mapped_column(
        String(30), default="active", nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    party_id: Mapped[int | None] = mapped_column(ForeignKey("parties.id"), nullable=True, index=True)

    patient_treatments: Mapped[list["PatientTreatment"]] = relationship(
        back_populates="patient", lazy="selectin"
    )
    invoices: Mapped[list["Invoice"]] = relationship(
        back_populates="patient", lazy="selectin"
    )
    party: Mapped["Party"] = relationship(lazy="selectin")

    __table_args__ = (
        UniqueConstraint("first_name", "last_name", "phone", name="uq_patient_identity"),
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<Patient {self.full_name}>"


class PatientTreatment(Base, TimestampMixin):
    __tablename__ = "patient_treatments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    treatment_id: Mapped[int] = mapped_column(
        ForeignKey("treatments.id"), nullable=False, index=True
    )
    treatment_date: Mapped[date] = mapped_column(nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_override_eur: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    patient: Mapped["Patient"] = relationship(back_populates="patient_treatments")
    treatment: Mapped["Treatment"] = relationship(back_populates="patient_treatments")

    @property
    def effective_price_eur(self) -> float:
        if self.price_override_eur is not None:
            return self.price_override_eur
        return self.treatment.price_eur

    def __repr__(self) -> str:
        return f"<PatientTreatment patient={self.patient_id} treatment={self.treatment_id}>"


class ExchangeRate(Base, TimestampMixin):
    __tablename__ = "exchange_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rate_date: Mapped[date] = mapped_column(nullable=False, index=True)
    eur_to_try: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="ecb", nullable=False)

    __table_args__ = (
        UniqueConstraint("rate_date", "source", name="uq_exchange_rate_date_source"),
    )

    def __repr__(self) -> str:
        return f"<ExchangeRate {self.rate_date}: 1€ = {self.eur_to_try:.2f}₺>"


class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id"), nullable=True, index=True)
    party_id: Mapped[int | None] = mapped_column(ForeignKey("parties.id"), nullable=True, index=True)
    invoice_number: Mapped[str] = mapped_column(String(30), nullable=False, unique=True, index=True)
    invoice_date: Mapped[date] = mapped_column(nullable=False, index=True)
    due_date: Mapped[date | None] = mapped_column(nullable=True)
    total_eur: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_try: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    exchange_rate: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    patient: Mapped["Patient"] = relationship(back_populates="invoices")
    party: Mapped["Party"] = relationship(back_populates="invoices")
    items: Mapped[list["InvoiceItem"]] = relationship(
        back_populates="invoice", lazy="selectin", cascade="all, delete-orphan"
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="invoice", lazy="selectin", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("invoice_number", name="uq_invoice_number"),
    )

    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"
    STATUS_OVERDUE = "overdue"
    STATUS_CANCELLED = "cancelled"

    def recalculate_totals(self) -> None:
        self.total_eur = sum(item.line_total_eur + item.vat_amount_eur for item in self.items)
        self.total_try = sum(item.line_total_try + item.vat_amount_try for item in self.items)

    def __repr__(self) -> str:
        return f"<Invoice {self.invoice_number} €{self.total_eur:.2f}>"


class InvoiceItem(Base, TimestampMixin):
    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_type: Mapped[str] = mapped_column(
        SQLEnum(InvoiceItemType), nullable=False, default=InvoiceItemType.TREATMENT
    )
    treatment_id: Mapped[int | None] = mapped_column(
        ForeignKey("treatments.id"), nullable=True, index=True
    )
    reference_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # for product/service/lab
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price_eur: Mapped[float] = mapped_column(Float, nullable=False)
    unit_price_try: Mapped[float] = mapped_column(Float, nullable=False)
    vat_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    discount_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # percent, amount
    discount_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    invoice: Mapped["Invoice"] = relationship(back_populates="items")
    treatment: Mapped["Treatment"] = relationship(back_populates="invoice_items")

    @property
    def line_total_eur(self) -> float:
        base = self.unit_price_eur * self.quantity
        if self.discount_type == "percent":
            return base * (1 - self.discount_value / 100)
        elif self.discount_type == "amount":
            return base - self.discount_value
        return base

    @property
    def line_total_try(self) -> float:
        base = self.unit_price_try * self.quantity
        if self.discount_type == "percent":
            return base * (1 - self.discount_value / 100)
        elif self.discount_type == "amount":
            return base - self.discount_value
        return base

    @property
    def vat_amount_eur(self) -> float:
        return self.line_total_eur * (self.vat_rate / 100)

    @property
    def vat_amount_try(self) -> float:
        return self.line_total_try * (self.vat_rate / 100)

    def __repr__(self) -> str:
        return f"<InvoiceItem {self.description} x{self.quantity} ({self.item_type.value})>"


class Settings(Base, TimestampMixin):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = ()

    DEFAULTS = {
        "clinic_name": "Makro Orto Denti",
        "clinic_address": "",
        "clinic_phone": "",
        "clinic_email": "",
        "clinic_logo_path": "",
        "tax_id": "",
        "invoice_prefix": "MKR",
        "invoice_next_number": "1",
        "invoice_footer_text": "",
        "default_exchange_rate_source": "ecb",
        "currency_symbol_eur": "€",
        "currency_symbol_try": "₺",
        "whatsapp_session_id": "",
        "whatsapp_phone_number": "",
    }

    def __repr__(self) -> str:
        return f"<Settings {self.key}={self.value}>"


class User(UserMixin, Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="staff", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    ROLE_ADMIN = "admin"
    ROLE_STAFF = "staff"
    VALID_ROLES = [ROLE_ADMIN, ROLE_STAFF]

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.role})>"


class WhatsAppSession(Base, TimestampMixin):
    __tablename__ = "whatsapp_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="disconnected", nullable=False)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    qr_code: Mapped[str | None] = mapped_column(Text, nullable=True)

    STATUS_DISCONNECTED = "disconnected"
    STATUS_CONNECTING = "connecting"
    STATUS_CONNECTED = "connected"

    def __repr__(self) -> str:
        return f"<WhatsAppSession {self.session_id} ({self.status})>"


class PaymentMethod(PyEnum):
    CASH = "cash"
    CARD = "card"
    TRANSFER = "transfer"
    CHECK = "check"
    OTHER = "other"


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False, index=True)
    payment_date: Mapped[date] = mapped_column(nullable=False, index=True)
    amount_eur: Mapped[float] = mapped_column(Float, nullable=False)
    amount_try: Mapped[float] = mapped_column(Float, nullable=False)
    exchange_rate: Mapped[float] = mapped_column(Float, nullable=False)
    method: Mapped[str] = mapped_column(SQLEnum(PaymentMethod), nullable=False, default=PaymentMethod.CASH)
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    invoice: Mapped["Invoice"] = relationship(lazy="selectin")

    def __repr__(self) -> str:
        return f"<Payment {self.invoice_id} €{self.amount_eur:.2f} ₺{self.amount_try:.2f}>"
