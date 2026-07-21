"""Tests for the WhatsApp makbuz send queue and the WhatsApp page makbuz panel.

WhatsApp/Neonize and PDF generation are always mocked.
"""

from __future__ import annotations

import time
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

from conftest import login

from app.extensions import db
from app.models.models import Makbuz, Party, PartyType, WorkOrder, money
from app.services.makbuz_send_queue import MakbuzSendQueue, send_makbuz_via_whatsapp
from app.services.whatsapp_service import WhatsAppService


def _wait_until(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def _seed_doctor_with_makbuz(app, name="Dr. Kuyruk", phone="+905551110001", status="draft"):
    with app.app_context():
        party = Party(party_type=PartyType.DENTIST, name=name, phone=phone)
        db.session.add(party)
        db.session.flush()
        db.session.add(WorkOrder(
            party_id=party.id, work_date=date(2026, 6, 12), apparatus_type="Nance",
            patient_name="Hasta", apparatus_price=Decimal("1000"),
            extra_price=Decimal("0"), total_price=Decimal("1000"),
        ))
        makbuz = Makbuz(
            party_id=party.id, year=2026, month=6, work_order_count=1,
            subtotal=money(Decimal("1000")), vat_applied=False,
            vat_rate=Decimal("0"), status=status,
            generated_at=datetime.now().astimezone(),
        )
        makbuz.recalculate_totals()
        db.session.add(makbuz)
        db.session.commit()
        return party.id, makbuz.id


class TestSendMakbuzViaWhatsApp:
    def test_success_marks_makbuz_sent(self, app):
        _, makbuz_id = _seed_doctor_with_makbuz(app)
        with app.app_context():
            with patch("app.services.makbuz_pdf_service.generate_makbuz_pdf", return_value=b"%PDF"):
                with patch.object(
                    WhatsAppService, "send_makbuz_message",
                    return_value={"success": True, "message": "ok"},
                ):
                    ok, message = send_makbuz_via_whatsapp(makbuz_id)
            assert ok is True
            makbuz = db.session.get(Makbuz, makbuz_id)
            assert makbuz.status == Makbuz.STATUS_SENT
            assert makbuz.sent_at is not None

    def test_failure_keeps_draft(self, app):
        _, makbuz_id = _seed_doctor_with_makbuz(app)
        with app.app_context():
            with patch("app.services.makbuz_pdf_service.generate_makbuz_pdf", return_value=b"%PDF"):
                with patch.object(
                    WhatsAppService, "send_makbuz_message",
                    return_value={"success": False, "message": "WhatsApp bağlı değil."},
                ):
                    ok, _ = send_makbuz_via_whatsapp(makbuz_id)
            assert ok is False
            assert db.session.get(Makbuz, makbuz_id).status == Makbuz.STATUS_DRAFT

    def test_missing_makbuz(self, app):
        with app.app_context():
            ok, message = send_makbuz_via_whatsapp(999999)
        assert ok is False
        assert "bulunamadı" in message


class TestQueue:
    def test_rejects_when_not_connected(self, app):
        _, makbuz_id = _seed_doctor_with_makbuz(app)
        with app.app_context():
            started, message = MakbuzSendQueue.start_batch([makbuz_id])
        assert started is False
        assert "bağlı değil" in message

    def test_rejects_empty_selection(self, app):
        with app.app_context():
            started, message = MakbuzSendQueue.start_batch([])
        assert started is False

    def test_rejects_unknown_ids(self, app):
        WhatsAppService._connected = True
        with app.app_context():
            started, message = MakbuzSendQueue.start_batch([987654])
        assert started is False
        assert "bulunamadı" in message

    def test_batch_processes_all_and_tracks_progress(self, app):
        WhatsAppService._connected = True
        MakbuzSendQueue._app = app
        _, m1 = _seed_doctor_with_makbuz(app, name="Dr. Bir", phone="+905551110001")
        _, m2 = _seed_doctor_with_makbuz(app, name="Dr. İki", phone="+905551110002")

        def fake_send(makbuz_id):
            return (makbuz_id == m1), "ok" if makbuz_id == m1 else "hata"

        with app.app_context():
            with patch(
                "app.services.makbuz_send_queue.send_makbuz_via_whatsapp",
                side_effect=fake_send,
            ):
                started, message = MakbuzSendQueue.start_batch([m1, m2])
                assert started is True
                assert "2 makbuz" in message
                assert _wait_until(lambda: not MakbuzSendQueue.is_running())

        job = MakbuzSendQueue.current_job()
        assert job["total"] == 2
        assert job["done"] == 2
        assert job["sent"] == 1
        assert job["failed"] == 1
        assert job["finished_at"] is not None
        by_doctor = {item["doctor"]: item for item in job["items"]}
        assert by_doctor["Dr. Bir"]["status"] == "sent"
        assert by_doctor["Dr. İki"]["status"] == "failed"
        assert by_doctor["Dr. İki"]["message"] == "hata"

    def test_only_one_batch_at_a_time(self, app):
        WhatsAppService._connected = True
        MakbuzSendQueue._app = app
        _, m1 = _seed_doctor_with_makbuz(app, name="Dr. Uzun", phone="+905551110003")

        import threading
        release = threading.Event()

        def slow_send(makbuz_id):
            release.wait(5)
            return True, "ok"

        with app.app_context():
            with patch(
                "app.services.makbuz_send_queue.send_makbuz_via_whatsapp",
                side_effect=slow_send,
            ):
                assert MakbuzSendQueue.start_batch([m1])[0] is True
                started, message = MakbuzSendQueue.start_batch([m1])
                assert started is False
                assert "Devam eden" in message
                release.set()
                assert _wait_until(lambda: not MakbuzSendQueue.is_running())

    def test_crash_marks_remaining_failed(self, app):
        WhatsAppService._connected = True
        MakbuzSendQueue._app = app
        _, m1 = _seed_doctor_with_makbuz(app, name="Dr. Kaza", phone="+905551110004")

        with app.app_context():
            with patch(
                "app.services.makbuz_send_queue.send_makbuz_via_whatsapp",
                side_effect=RuntimeError("beklenmedik"),
            ):
                assert MakbuzSendQueue.start_batch([m1])[0] is True
                assert _wait_until(lambda: not MakbuzSendQueue.is_running())

        job = MakbuzSendQueue.current_job()
        assert job["failed"] == 1
        assert job["items"][0]["status"] == "failed"

    def test_clear_finished(self, app):
        MakbuzSendQueue._job = {"running": False, "items": []}
        MakbuzSendQueue.clear_finished()
        assert MakbuzSendQueue.current_job() is None


class TestWhatsAppMakbuzPanel:
    def test_index_lists_candidates_for_period(self, client, app):
        login(client, "admin", "admin-pass")
        _seed_doctor_with_makbuz(app, name="Dr. Panel", phone="+905551110005")
        response = client.get("/whatsapp/?year=2026&month=6")
        assert response.status_code == 200
        assert "Dr. Panel".encode() in response.data
        assert b"wa-select-all" in response.data
        assert "Makbuz Gönderimi".encode() in response.data

    def test_index_empty_period_shows_hint(self, client, app):
        login(client, "admin", "admin-pass")
        response = client.get("/whatsapp/?year=2020&month=2")
        assert response.status_code == 200
        assert "oluşturulmuş makbuz bulunmuyor".encode() in response.data

    def test_index_counts_doctors_without_makbuz(self, client, app):
        login(client, "admin", "admin-pass")
        with app.app_context():
            party = Party(party_type=PartyType.DENTIST, name="Dr. Makbuzsuz", phone="+905551110006")
            db.session.add(party)
            db.session.flush()
            db.session.add(WorkOrder(
                party_id=party.id, work_date=date(2026, 5, 5), apparatus_type="Nance",
                patient_name="Hasta", apparatus_price=Decimal("500"),
                extra_price=Decimal("0"), total_price=Decimal("500"),
            ))
            db.session.commit()
        response = client.get("/whatsapp/?year=2026&month=5")
        assert "makbuzu henüz".encode() in response.data

    def test_batch_route_starts_queue(self, client, app):
        login(client, "admin", "admin-pass")
        with patch.object(
            MakbuzSendQueue, "start_batch", return_value=(True, "3 makbuz için gönderim arka planda başlatıldı.")
        ) as mock_start:
            response = client.post(
                "/whatsapp/send-makbuz-batch",
                data={"year": "2026", "month": "6", "makbuz_ids": ["1", "2", "3"]},
                follow_redirects=True,
            )
        assert response.status_code == 200
        mock_start.assert_called_once_with([1, 2, 3])
        assert "arka planda".encode() in response.data

    def test_batch_route_reports_failure(self, client, app):
        login(client, "admin", "admin-pass")
        response = client.post(
            "/whatsapp/send-makbuz-batch",
            data={"year": "2026", "month": "6"},
            follow_redirects=True,
        )
        assert "makbuz seçilmedi".encode() in response.data

    def test_status_endpoint_includes_job(self, client, app):
        login(client, "admin", "admin-pass")
        MakbuzSendQueue._job = {
            "id": "x", "running": True, "total": 2, "done": 1, "sent": 1,
            "failed": 0, "items": [], "started_at": "", "finished_at": None,
        }
        data = client.get("/whatsapp/status").get_json()
        assert data["send_job"]["total"] == 2
        assert data["send_job"]["running"] is True


class TestStatusIndicators:
    def test_quick_state_disconnected_by_default(self, app):
        assert WhatsAppService.quick_state() == "disconnected"

    def test_quick_state_connected(self, app):
        WhatsAppService._connected = True
        assert WhatsAppService.quick_state() == "connected"

    def test_sidebar_shows_status_dot(self, client, app):
        login(client, "admin", "admin-pass")
        response = client.get("/whatsapp/")
        assert b"wa-status-dot" in response.data
        assert b"wa-status-disconnected" in response.data

    def test_dashboard_banner_when_disconnected(self, client, app):
        login(client, "admin", "admin-pass")
        response = client.get("/")
        assert b"wa-connect-banner" in response.data
        assert "WhatsApp bağlı değil".encode() in response.data

    def test_dashboard_banner_hidden_when_connected(self, client, app):
        login(client, "admin", "admin-pass")
        WhatsAppService._connected = True
        response = client.get("/")
        assert b"wa-connect-banner" not in response.data
        assert b"wa-status-connected" in response.data
