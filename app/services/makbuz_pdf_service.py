import json
import os

from fpdf import FPDF
from fpdf.enums import XPos, YPos

CURRENCY_SYMBOLS = {"TL": "₺", "EUR": "€", "USD": "$"}


def _format_items(raw: str | None) -> str:
    """Render a WorkOrder apparatus_type/extra_addons field for display.

    The field stores either a JSON array of {name, price, currency} objects
    (selected from the treatment catalog) or, for legacy rows, a plain
    description string.
    """
    if not raw:
        return ""
    try:
        items = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw
    if not isinstance(items, list) or not items:
        return raw
    parts = []
    for item in items:
        if isinstance(item, dict):
            symbol = CURRENCY_SYMBOLS.get(item.get("currency", "TL"), "₺")
            parts.append(f"{item.get('name', '')} ({symbol}{float(item.get('price', 0)):,.2f})")
        else:
            parts.append(str(item))
    return ", ".join(parts)

FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "fonts")
FONT_PATH = os.path.join(FONT_DIR, "DejaVuSans.ttf")
FONT_PATH_BOLD = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")
LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "images", "brand-mark.svg")

MONTH_NAMES = [
    "", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
]


class MakbuzPDF(FPDF):
    INK = (16, 46, 58)
    MUTED = (88, 113, 123)
    AQUA_DARK = (24, 140, 138)
    SKY_PALE = (235, 247, 250)
    LINE = (220, 232, 233)
    SURFACE = (247, 250, 250)

    def __init__(self, clinic_name="Makro Ortodonti", clinic_phone="", clinic_email=""):
        super().__init__()
        self.clinic_name = clinic_name
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
                self.default_font = "Helvetica"
        self.set_margins(12, 15, 12)
        self.set_auto_page_break(auto=True, margin=24)

    def _safe_text(self, text):
        value = "" if text is None else str(text)
        if self.default_font == "DejaVu":
            return value
        replacements = {
            "₺": "TRY ", "€": "EUR ", "ı": "i", "İ": "I", "ş": "s",
            "Ş": "S", "ğ": "g", "Ğ": "G", "ü": "u", "Ü": "U",
            "ö": "o", "Ö": "O", "ç": "c", "Ç": "C",
        }
        for source, target in replacements.items():
            value = value.replace(source, target)
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
        try:
            self.image(LOGO_PATH, x=12, y=9.5, w=18, h=18, keep_aspect_ratio=True)
        except Exception:
            self.set_fill_color(*self.AQUA_DARK)
            self.rect(12, 10, 17, 17, style="F")
            self.set_xy(12, 10.5)
            self.set_font(self.default_font, "B", 13)
            self.set_text_color(255, 255, 255)
            self.cell(17, 16, "M", align="C")

        self.set_xy(35, 10)
        self.set_font(self.default_font, "B", 15)
        self.set_text_color(*self.INK)
        self.cell(104, 7, self.clinic_name)
        self.set_xy(35, 18)
        self.set_font(self.default_font, "", 7.5)
        self.set_text_color(*self.MUTED)
        contacts = [value for value in (self.clinic_phone, self.clinic_email) if value]
        self.cell(104, 5, "  |  ".join(contacts) or "Ortodonti ve klinik hizmetleri")

        self.set_xy(145, 10)
        self.set_font(self.default_font, "B", 16)
        self.set_text_color(*self.AQUA_DARK)
        self.cell(53, 8, "MAKBUZ", align="R")

        self.set_draw_color(*self.LINE)
        self.set_line_width(.35)
        self.line(12, 32, 198, 32)
        self.set_y(38)

    def footer(self):
        self.set_y(-19)
        self.set_draw_color(*self.LINE)
        self.line(12, self.get_y(), 198, self.get_y())
        self.ln(2)
        self.set_font(self.default_font, "", 6.5)
        self.set_text_color(*self.MUTED)
        self.cell(140, 6, "Bu belge elektronik ortamda oluşturulmuştur.")
        self.cell(46, 6, f"Sayfa {self.page_no()}/{{nb}}", align="R")

    def add_summary(self, makbuz, doctor_name):
        y = self.get_y()
        self.set_fill_color(*self.SURFACE)
        self.set_draw_color(*self.LINE)
        self.rect(12, y, 186, 24, style="DF")

        self.set_xy(18, y + 5)
        self.set_font(self.default_font, "B", 7)
        self.set_text_color(*self.AQUA_DARK)
        self.cell(90, 5, "MAKBUZ EDİLEN DOKTOR")
        self.set_xy(18, y + 11)
        self.set_font(self.default_font, "B", 11)
        self.set_text_color(*self.INK)
        self.cell(90, 6, doctor_name[:48])

        period = f"{MONTH_NAMES[makbuz.month]} {makbuz.year}"
        self.set_xy(118, y + 5)
        self.set_font(self.default_font, "", 6.7)
        self.set_text_color(*self.MUTED)
        self.cell(35, 5, "Dönem")
        self.set_font(self.default_font, "B", 6.7)
        self.set_text_color(*self.INK)
        self.cell(33, 5, period, align="R")

        self.set_xy(118, y + 11)
        self.set_font(self.default_font, "", 6.7)
        self.set_text_color(*self.MUTED)
        self.cell(35, 5, "İş emri sayısı")
        self.set_font(self.default_font, "B", 6.7)
        self.set_text_color(*self.INK)
        self.cell(33, 5, str(makbuz.work_order_count), align="R")

        self.set_xy(118, y + 17)
        self.set_font(self.default_font, "", 6.7)
        self.set_text_color(*self.MUTED)
        self.cell(35, 5, "Düzenlenme tarihi")
        self.set_font(self.default_font, "B", 6.7)
        self.set_text_color(*self.INK)
        self.cell(33, 5, makbuz.generated_at.strftime("%d.%m.%Y"), align="R")

        self.set_y(y + 30)

    def _table_header(self):
        widths = (24, 55, 45, 31, 31)
        labels = ("Tarih", "Hasta", "Aparey / Ekstra", "Aparey (₺)", "Toplam (₺)")
        self.set_fill_color(*self.INK)
        self.set_text_color(255, 255, 255)
        self.set_font(self.default_font, "B", 7)
        for width, label in zip(widths, labels):
            align = "R" if label in ("Aparey (₺)", "Toplam (₺)") else "L"
            self.cell(width, 8, label, border=0, fill=True, align=align)
        self.ln()

    def add_items_table(self, work_orders):
        self.set_font(self.default_font, "B", 9)
        self.set_text_color(*self.AQUA_DARK)
        self.cell(0, 7, "İŞ EMİRLERİ", ln=True)
        self._table_header()
        widths = (24, 55, 45, 31, 31)
        for index, wo in enumerate(work_orders):
            if self.get_y() > 255:
                self.add_page()
                self._table_header()
            detail = _format_items(wo.apparatus_type)
            extra_detail = _format_items(wo.extra_addons)
            if extra_detail:
                detail = f"{detail} + {extra_detail}" if detail else extra_detail
            self.set_fill_color(*(self.SURFACE if index % 2 == 0 else (255, 255, 255)))
            self.set_text_color(*self.INK)
            self.set_font(self.default_font, "", 7.2)
            values = (
                wo.work_date.strftime("%d.%m.%Y"),
                wo.patient_name[:32],
                detail[:38],
                f"{wo.apparatus_price:,.2f}",
                f"{wo.total_price:,.2f}",
            )
            for width, value in zip(widths, values):
                align = "R" if width == 31 else "L"
                self.cell(width, 8, value, border="B", fill=True, align=align)
            self.ln()

    def add_totals(self, makbuz):
        if self.get_y() > 225:
            self.add_page()
        self.ln(4)
        x_label, x_value = 126, 163
        rows = [("Ara toplam", f"₺{makbuz.subtotal:,.2f}", False)]
        if makbuz.vat_applied:
            rows.append((f"KDV (%{makbuz.vat_rate:,.2f})", f"₺{makbuz.vat_amount:,.2f}", False))
        for label, value, bold in rows:
            self.set_xy(x_label, self.get_y())
            self.set_font(self.default_font, "B" if bold else "", 8)
            self.set_text_color(*self.MUTED if not bold else self.INK)
            self.cell(37, 7, label, align="R")
            self.set_text_color(*self.INK)
            self.cell(35, 7, value, align="R")
            self.ln()

        self.set_x(126)
        self.set_fill_color(*self.AQUA_DARK)
        self.set_text_color(255, 255, 255)
        self.set_font(self.default_font, "B", 10)
        self.cell(37, 11, "GENEL TOPLAM", fill=True, align="R")
        self.cell(35, 11, f"₺{makbuz.grand_total:,.2f}", fill=True, align="R")
        self.ln()


def generate_makbuz_pdf(makbuz, work_orders) -> bytes:
    from app.extensions import db
    from app.models.models import Settings

    def get_setting(key, default=""):
        value = db.session.execute(
            db.select(Settings.value).where(Settings.key == key)
        ).scalar_one_or_none()
        return value or default

    pdf = MakbuzPDF(
        clinic_name=get_setting("clinic_name", "Makro Ortodonti"),
        clinic_phone=get_setting("clinic_phone"),
        clinic_email=get_setting("clinic_email"),
    )
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.add_summary(makbuz, makbuz.party.name if makbuz.party else "Bilinmeyen doktor")
    pdf.add_items_table(work_orders)
    pdf.add_totals(makbuz)

    output = pdf.output()
    return bytes(output) if isinstance(output, (bytes, bytearray)) else str(output).encode("latin-1", errors="ignore")
