"""WhatsApp service using Neonize for free message sending."""

import os
import json
import asyncio
import threading
from datetime import datetime, timezone
from typing import Optional

from app.extensions import db
from app.models.models import WhatsAppSession, Settings


class WhatsAppService:
    _client = None
    _connected = False
    _qr_code = None
    _session_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

    @classmethod
    def get_client(cls):
        if cls._client is None:
            try:
                from neonize.client import NewClient
                db_path = os.path.join(cls._session_dir, "whatsapp_session.db")
                cls._client = NewClient(db_path)
            except Exception as e:
                print(f"WhatsApp client creation error: {e}")
                return None
        return cls._client

    @classmethod
    def connect(cls, phone_number: Optional[str] = None) -> dict:
        """Connect to WhatsApp. Returns QR code or pair code status."""
        try:
            client = cls.get_client()
            if client is None:
                return {"success": False, "message": "WhatsApp istemcisi oluşturulamadı."}

            session = db.session.execute(
                db.select(WhatsAppSession).where(
                    WhatsAppSession.session_id == "default"
                )
            ).scalar_one_or_none()

            if not session:
                session = WhatsAppSession(
                    session_id="default",
                    status=WhatsAppSession.STATUS_CONNECTING,
                )
                db.session.add(session)
                db.session.commit()

            session.status = WhatsAppSession.STATUS_CONNECTING
            db.session.commit()

            if phone_number:
                # Pair code authentication
                try:
                    client.pair_phone_code(phone_number)
                    session.phone_number = phone_number
                    session.status = WhatsAppSession.STATUS_CONNECTED
                    session.connected_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    db.session.commit()
                    cls._connected = True
                    return {"success": True, "message": "WhatsApp bağlandı (pair code)."}
                except Exception as e:
                    session.status = WhatsAppSession.STATUS_DISCONNECTED
                    db.session.commit()
                    return {"success": False, "message": f"Bağlantı hatası: {str(e)}"}
            else:
                return {"success": True, "message": "QR kod bekleniyor. Lütfen WhatsApp'tan QR kodu tarayın."}

        except Exception as e:
            return {"success": False, "message": f"Hata: {str(e)}"}

    @classmethod
    def disconnect(cls) -> dict:
        try:
            session = db.session.execute(
                db.select(WhatsAppSession).where(
                    WhatsAppSession.session_id == "default"
                )
            ).scalar_one_or_none()

            if session:
                session.status = WhatsAppSession.STATUS_DISCONNECTED
                session.disconnected_at = datetime.now(timezone.utc).replace(tzinfo=None)
                db.session.commit()

            cls._connected = False
            return {"success": True, "message": "WhatsApp bağlantısı kesildi."}
        except Exception as e:
            return {"success": False, "message": f"Hata: {str(e)}"}

    @classmethod
    def get_status(cls) -> dict:
        try:
            session = db.session.execute(
                db.select(WhatsAppSession).where(
                    WhatsAppSession.session_id == "default"
                )
            ).scalar_one_or_none()

            return {
                "connected": cls._connected,
                "status": session.status if session else "disconnected",
                "phone_number": session.phone_number if session else None,
                "connected_at": session.connected_at if session else None,
            }
        except Exception:
            return {"connected": False, "status": "disconnected", "phone_number": None, "connected_at": None}

    @classmethod
    def send_message(cls, phone_number: str, message: str) -> dict:
        """Send a text message to a phone number."""
        try:
            if not cls._connected:
                return {"success": False, "message": "WhatsApp bağlı değil."}

            client = cls.get_client()
            if client is None:
                return {"success": False, "message": "WhatsApp istemcisi mevcut değil."}

            # Format phone number for WhatsApp JID
            clean_phone = phone_number.replace("+", "").replace(" ", "").replace("-", "")
            if not clean_phone.endswith("@s.whatsapp.net"):
                jid = f"{clean_phone}@s.whatsapp.net"
            else:
                jid = clean_phone

            client.send_message(jid, message)
            return {"success": True, "message": f"Mesaj gönderildi: {phone_number}"}

        except Exception as e:
            return {"success": False, "message": f"Gönderim hatası: {str(e)}"}

    @classmethod
    def send_invoice_message(cls, invoice) -> dict:
        """Send invoice notification to customer via WhatsApp."""
        # Support both party and legacy patient invoices
        phone = None
        name = None
        if invoice.party and invoice.party.phone:
            phone = invoice.party.phone
            name = invoice.party.display_name
        elif invoice.patient and invoice.patient.phone:
            phone = invoice.patient.phone
            name = invoice.patient.full_name

        if not phone:
            return {"success": False, "message": "Müşterinin telefon numarası bulunmuyor."}

        status_tr = {
            "pending": "Bekliyor",
            "paid": "Ödendi",
            "overdue": "Gecikmiş",
            "cancelled": "İptal",
        }

        message = f"""Sayın {name},

{invoice.invoice_date.strftime('%d.%m.%Y')} tarihli {invoice.invoice_number} numaralı faturanız hazırlanmıştır.

Toplam Tutar: ₺{invoice.total_try:,.2f} (€{invoice.total_eur:,.2f})
Durum: {status_tr.get(invoice.status, invoice.status)}
{"Son Ödeme: " + invoice.due_date.strftime('%d.%m.%Y') if invoice.due_date else ""}

Faturanız ekte gönderilmiştir.

Saygılarımızla,
Makro Ortodonti"""

        return cls.send_message(phone, message)

    @classmethod
    def send_reminder(cls, patient, message: str) -> dict:
        """Send a custom reminder message to a patient."""
        if not patient.phone:
            return {"success": False, "message": "Hastanın telefon numarası bulunmuyor."}

        return cls.send_message(patient.phone, message)
