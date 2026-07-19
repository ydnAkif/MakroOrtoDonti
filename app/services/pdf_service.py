import os
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from datetime import date


FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "fonts")
FONT_PATH = os.path.join(FONT_DIR, "DejaVuSans.ttf")
FONT_PATH_BOLD = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")


class InvoicePDF(FPDF):
    def __init__(self, clinic_name="Makro Ortodonti", clinic_address="", clinic_phone="", clinic_email=""):
        super().__init__()
        self.clinic_name = clinic_name
        self.clinic_address = clinic_address
        self.clinic_phone = clinic_phone
        self.clinic_email = clinic_email

        self.default_font = "Helvetica"
        if os.path.exists(FONT_PATH):
            try:
                self.add_font("DejaVu", "", FONT_PATH)
                if os.path.exists(FONT_PATH_BOLD):
                    self.add_font("DejaVu", "B", FONT_PATH_BOLD)
                self.default_font = "DejaVu"
            except Exception:
                # If custom font files are invalid/corrupt, continue with a core font.
                self.default_font = "Helvetica"

    def _safe_text(self, text):
        if text is None:
            return ""
        value = str(text)
        if self.default_font == "DejaVu":
            return value

        # Core fonts cannot reliably render all Unicode characters.
        replacements = {
            "₺": "TRY ",
            "€": "EUR ",
            "ı": "i",
            "İ": "I",
            "ş": "s",
            "Ş": "S",
            "ğ": "g",
            "Ğ": "G",
            "ü": "u",
            "Ü": "U",
            "ö": "o",
            "Ö": "O",
            "ç": "c",
            "Ç": "C",
        }
        for src, target in replacements.items():
            value = value.replace(src, target)

        return value.encode("cp1252", errors="replace").decode("cp1252")

    def cell(self, w=0, h=0, text="", *args, **kwargs):
        if kwargs.pop("ln", False):
            kwargs.setdefault("new_x", XPos.LMARGIN)
            kwargs.setdefault("new_y", YPos.NEXT)
        return super().cell(w, h, self._safe_text(text), *args, **kwargs)

    def multi_cell(self, w, h, text="", *args, **kwargs):
        if kwargs.pop("ln", False):
            kwargs.setdefault("new_x", XPos.LMARGIN)
            kwargs.setdefault("new_y", YPos.NEXT)
        return super().multi_cell(w, h, self._safe_text(text), *args, **kwargs)

    def header(self):
        self.set_font(self.default_font, "B", 18)
        self.set_text_color(0, 102, 153)
        self.cell(0, 10, self.clinic_name, ln=True, align="C")
        self.set_font(self.default_font, "", 9)
        self.set_text_color(100, 100, 100)
        if self.clinic_address:
            self.cell(0, 5, self.clinic_address, ln=True, align="C")
        if self.clinic_phone:
            self.cell(0, 5, f"Tel: {self.clinic_phone}", ln=True, align="C")
        if self.clinic_email:
            self.cell(0, 5, f"E-posta: {self.clinic_email}", ln=True, align="C")
        self.ln(5)
        self.set_draw_color(0, 102, 153)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font(self.default_font, "", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Sayfa {self.page_no()}/{{nb}}", align="C")

    def add_invoice_info(self, invoice_number, invoice_date, due_date, status):
        self.set_font(self.default_font, "B", 14)
        self.set_text_color(0, 0, 0)
        self.cell(0, 10, "FATURA", ln=True, align="R")

        self.set_font(self.default_font, "", 10)
        self.set_text_color(80, 80, 80)
        self.cell(0, 6, f"Fatura No: {invoice_number}", ln=True, align="R")
        self.cell(0, 6, f"Tarih: {invoice_date.strftime('%d.%m.%Y') if hasattr(invoice_date, 'strftime') else str(invoice_date)}", ln=True, align="R")
        if due_date:
            self.cell(0, 6, f"Son Ödeme: {due_date.strftime('%d.%m.%Y') if hasattr(due_date, 'strftime') else str(due_date)}", ln=True, align="R")

        status_tr = {
            "pending": "Bekliyor",
            "paid": "Ödendi",
            "overdue": "Gecikmiş",
            "cancelled": "İptal",
        }
        self.cell(0, 6, f"Durum: {status_tr.get(status, status)}", ln=True, align="R")
        self.ln(5)

    def add_patient_info(self, patient):
        """Legacy method for backward compatibility."""
        self.add_customer_info({
            "name": patient.full_name,
            "phone": patient.phone,
            "email": patient.email,
            "address": patient.address,
        })

    def add_customer_info(self, customer):
        """Add customer info (works for both patient and party)."""
        self.set_font(self.default_font, "B", 11)
        self.set_text_color(0, 102, 153)
        self.cell(0, 8, "Müşteri Bilgileri", ln=True)
        self.set_draw_color(0, 102, 153)
        self.line(10, self.get_y(), 80, self.get_y())
        self.ln(3)

        self.set_font(self.default_font, "", 10)
        self.set_text_color(0, 0, 0)
        self.cell(0, 6, f"Ad Soyad: {customer['name']}", ln=True)
        if customer.get('phone'):
            self.cell(0, 6, f"Telefon: {customer['phone']}", ln=True)
        if customer.get('email'):
            self.cell(0, 6, f"E-posta: {customer['email']}", ln=True)
        if customer.get('address'):
            self.cell(0, 6, f"Adres: {customer['address']}", ln=True)
        self.ln(5)

    def add_items_table(self, items, exchange_rate):
        self.set_font(self.default_font, "B", 11)
        self.set_text_color(0, 102, 153)
        self.cell(0, 8, "Tedavi Detayları", ln=True)
        self.set_draw_color(0, 102, 153)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)

        self.set_font(self.default_font, "B", 9)
        self.set_fill_color(0, 102, 153)
        self.set_text_color(255, 255, 255)
        self.cell(80, 8, "Tedavi", border=1, fill=True)
        self.cell(15, 8, "Adet", border=1, fill=True, align="C")
        self.cell(35, 8, "Birim (EUR)", border=1, fill=True, align="R")
        self.cell(35, 8, "Birim (TRY)", border=1, fill=True, align="R")
        self.cell(25, 8, "Toplam (TRY)", border=1, fill=True, align="R")
        self.ln()

        self.set_font(self.default_font, "", 9)
        self.set_text_color(0, 0, 0)
        fill = False
        for item in items:
            if fill:
                self.set_fill_color(240, 248, 255)
            else:
                self.set_fill_color(255, 255, 255)

            self.cell(80, 7, item.description[:40], border=1, fill=True)
            self.cell(15, 7, str(item.quantity), border=1, fill=True, align="C")
            self.cell(35, 7, f"€{item.unit_price_eur:,.2f}", border=1, fill=True, align="R")
            self.cell(35, 7, f"₺{item.unit_price_try:,.2f}", border=1, fill=True, align="R")
            self.cell(25, 7, f"₺{item.line_total_try:,.2f}", border=1, fill=True, align="R")
            self.ln()
            fill = not fill

    def add_totals(self, total_eur, total_try, exchange_rate):
        self.ln(5)
        self.set_font(self.default_font, "", 10)
        self.set_text_color(80, 80, 80)

        self.cell(130, 7, "Kur (1 EUR =)", align="R")
        self.cell(50, 7, f"₺{exchange_rate:,.4f}", align="R")
        self.ln()

        self.set_font(self.default_font, "B", 11)
        self.set_text_color(0, 102, 153)
        self.cell(130, 8, "Toplam (EUR):", align="R")
        self.cell(50, 8, f"€{total_eur:,.2f}", align="R")
        self.ln()

        self.set_font(self.default_font, "B", 13)
        self.set_text_color(0, 0, 0)
        self.cell(130, 10, "TOPLAM (TRY):", align="R")
        self.cell(50, 10, f"₺{total_try:,.2f}", align="R")
        self.ln()

    def add_notes(self, notes):
        if notes:
            self.ln(5)
            self.set_font(self.default_font, "B", 10)
            self.set_text_color(0, 102, 153)
            self.cell(0, 7, "Notlar:", ln=True)
            self.set_font(self.default_font, "", 9)
            self.set_text_color(80, 80, 80)
            self.multi_cell(0, 5, notes)


def get_customer_info(invoice):
    """Get customer info from either party (preferred) or legacy patient."""
    if invoice.party:
        return {
            "name": invoice.party.display_name,
            "phone": invoice.party.phone,
            "email": invoice.party.email,
            "address": invoice.party.address,
        }
    elif invoice.patient:
        return {
            "name": invoice.patient.full_name,
            "phone": invoice.patient.phone,
            "email": invoice.patient.email,
            "address": invoice.patient.address,
        }
    return {"name": "Bilinmeyen Müşteri", "phone": None, "email": None, "address": None}


def generate_invoice_pdf(invoice) -> bytes:
    from app.extensions import db
    from app.models.models import Settings

    def get_setting(key, default=""):
        val = db.session.execute(
            db.select(Settings.value).where(Settings.key == key)
        ).scalar_one_or_none()
        return val or default

    clinic_name_val = get_setting("clinic_name", "Makro Ortodonti")
    clinic_address_val = get_setting("clinic_address")
    clinic_phone_val = get_setting("clinic_phone")
    clinic_email_val = get_setting("clinic_email")

    pdf = InvoicePDF(
        clinic_name=clinic_name_val,
        clinic_address=clinic_address_val,
        clinic_phone=clinic_phone_val,
        clinic_email=clinic_email_val,
    )
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.add_invoice_info(
        invoice.invoice_number,
        invoice.invoice_date,
        invoice.due_date,
        invoice.status,
    )
    
    customer = get_customer_info(invoice)
    pdf.add_customer_info(customer)
    pdf.add_items_table(invoice.items, invoice.exchange_rate)
    pdf.add_totals(invoice.total_eur, invoice.total_try, invoice.exchange_rate)
    pdf.add_notes(invoice.notes)

    output = pdf.output()
    if isinstance(output, bytearray):
        return bytes(output)
    if isinstance(output, bytes):
        return output
    return str(output).encode("latin-1", errors="ignore")
