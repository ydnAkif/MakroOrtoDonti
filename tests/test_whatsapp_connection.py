"""Tests for the Neonize-backed WhatsApp connection flow.

Neonize is always mocked — no real WhatsApp account or network is used.
"""

from __future__ import annotations

import os
import threading
import time
from unittest.mock import MagicMock, patch

from conftest import login

from app.extensions import db
from app.models.models import WhatsAppSession
from app.services.whatsapp_service import WhatsAppService


def _wait_until(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


class TestStart:
    def test_start_registers_handlers_and_connects(self, app):
        mock_client = MagicMock()
        with patch.object(WhatsAppService, "get_client", return_value=mock_client):
            assert WhatsAppService.start() is True

        assert _wait_until(lambda: mock_client.connect.called)
        # Raw QR callback + Connected/PairStatus/Disconnected/LoggedOut events
        mock_client.event.qr.assert_called_once_with(WhatsAppService._on_qr)
        registered = [call.args[0].__name__ for call in mock_client.event.call_args_list]
        assert "Connected" in registered
        assert "PairStatus" in registered
        assert "Disconnected" in registered
        assert "LoggedOut" in registered

    def test_start_is_idempotent_while_thread_alive(self, app):
        mock_client = MagicMock()
        release = threading.Event()
        mock_client.connect.side_effect = lambda: release.wait(5)
        with patch.object(WhatsAppService, "get_client", return_value=mock_client):
            assert WhatsAppService.start() is True
            assert WhatsAppService.start() is True
        assert mock_client.connect.call_count <= 1 or _wait_until(
            lambda: mock_client.connect.call_count == 1
        )
        release.set()

    def test_start_refused_without_process_lock(self, app):
        with patch.object(WhatsAppService, "_acquire_process_lock", return_value=False):
            assert WhatsAppService.start() is False

    def test_process_lock_reentrant_in_same_process(self, app):
        assert WhatsAppService._acquire_process_lock() is True
        assert WhatsAppService._acquire_process_lock() is True


class TestEventHandlers:
    def test_on_qr_stores_payload_and_db_row(self, app):
        WhatsAppService._app = app
        WhatsAppService._on_qr(MagicMock(), b"2@qr-payload-data")

        assert WhatsAppService._qr_code == "2@qr-payload-data"
        with app.app_context():
            row = db.session.execute(
                db.select(WhatsAppSession).where(WhatsAppSession.session_id == "default")
            ).scalar_one()
            assert row.status == WhatsAppSession.STATUS_CONNECTING
            assert row.qr_code == "2@qr-payload-data"

    def test_on_connected_marks_session_connected(self, app):
        WhatsAppService._app = app
        WhatsAppService._qr_code = "2@old-qr"
        client = MagicMock()
        client.me.JID.User = "905551112233"

        WhatsAppService._on_connected(client, None)

        assert WhatsAppService._connected is True
        assert WhatsAppService._qr_code is None
        with app.app_context():
            row = db.session.execute(
                db.select(WhatsAppSession).where(WhatsAppSession.session_id == "default")
            ).scalar_one()
            assert row.status == WhatsAppSession.STATUS_CONNECTED
            assert row.connected_at is not None
            assert row.qr_code is None
            assert row.phone_number == "905551112233"

    def test_on_logged_out_resets_session(self, app):
        WhatsAppService._app = app
        WhatsAppService._connected = True
        WhatsAppService._on_logged_out(MagicMock(), None)

        assert WhatsAppService._connected is False
        with app.app_context():
            row = db.session.execute(
                db.select(WhatsAppSession).where(WhatsAppSession.session_id == "default")
            ).scalar_one()
            assert row.status == WhatsAppSession.STATUS_DISCONNECTED
            assert row.disconnected_at is not None

    def test_on_disconnected_blocks_sends(self, app):
        WhatsAppService._connected = True
        WhatsAppService._on_disconnected(MagicMock(), None)
        assert WhatsAppService._connected is False
        result = WhatsAppService.send_message("+905551112233", "test")
        assert result["success"] is False


class TestStatus:
    def test_status_includes_qr_image_data_uri(self, app):
        WhatsAppService._qr_code = "2@qr-payload"
        with app.app_context():
            status = WhatsAppService.get_status()
        assert status["qr"] == "2@qr-payload"
        assert status["qr_image"].startswith("data:image/png;base64,")
        assert status["connected"] is False

    def test_status_endpoint_returns_qr_json(self, client, app):
        login(client, "admin", "admin-pass")
        WhatsAppService._qr_code = "2@qr-payload"
        response = client.get("/whatsapp/status")
        assert response.status_code == 200
        data = response.get_json()
        assert data["qr"] == "2@qr-payload"
        assert data["qr_image"].startswith("data:image/png;base64,")
        assert data["connected"] is False

    def test_status_endpoint_when_connected(self, client, app):
        login(client, "admin", "admin-pass")
        WhatsAppService._app = app
        client_mock = MagicMock()
        client_mock.me.JID.User = "905551112233"
        WhatsAppService._on_connected(client_mock, None)

        response = client.get("/whatsapp/status")
        data = response.get_json()
        assert data["connected"] is True
        assert data["status"] == "connected"
        assert data["qr"] is None
        assert data["phone_number"] == "905551112233"
        assert data["connected_at"]  # isoformat string

    def test_index_page_renders_qr_polling(self, client, app):
        login(client, "admin", "admin-pass")
        response = client.get("/whatsapp/")
        assert response.status_code == 200
        assert b"wa-qr-area" in response.data
        assert b"/whatsapp/status" in response.data


class TestAutoReconnect:
    def test_init_app_starts_when_session_db_exists(self, app):
        with open(WhatsAppService.session_db_path(), "wb") as f:
            f.write(b"")
        app.testing = False
        old_debug = app.debug
        app.debug = False  # debug without WERKZEUG_RUN_MAIN means reloader parent
        try:
            with patch.object(WhatsAppService, "start") as mock_start:
                WhatsAppService.init_app(app)
                assert _wait_until(lambda: mock_start.called)
        finally:
            app.testing = True
            app.debug = old_debug

    def test_init_app_skips_without_session_db(self, app):
        assert not os.path.exists(WhatsAppService.session_db_path())
        app.testing = False
        try:
            with patch.object(WhatsAppService, "start") as mock_start:
                WhatsAppService.init_app(app)
                time.sleep(0.2)
                assert not mock_start.called
        finally:
            app.testing = True

    def test_init_app_skips_in_testing_mode(self, app):
        with open(WhatsAppService.session_db_path(), "wb") as f:
            f.write(b"")
        with patch.object(WhatsAppService, "start") as mock_start:
            WhatsAppService.init_app(app)
            time.sleep(0.2)
            assert not mock_start.called


class TestConnectFlow:
    def test_connect_without_phone_starts_qr_flow(self, app):
        with app.app_context():
            with patch.object(WhatsAppService, "start", return_value=True) as mock_start:
                result = WhatsAppService.connect()
        assert result["success"] is True
        assert "QR" in result["message"]
        mock_start.assert_called_once()

    def test_connect_with_phone_requests_pair_code(self, app):
        mock_client = MagicMock()
        mock_client.PairPhone.return_value = "ABCD-1234"
        WhatsAppService._client = mock_client
        WhatsAppService._qr_code = "2@qr"  # socket already in pairing mode
        WhatsAppService._app = app

        with app.app_context():
            with patch.object(WhatsAppService, "start", return_value=True):
                result = WhatsAppService.connect(phone_number="+90 555 123 45 67")
        assert result["success"] is True
        assert _wait_until(lambda: WhatsAppService._pair_code == "ABCD-1234")
        mock_client.PairPhone.assert_called_once_with(
            "905551234567", show_push_notification=True
        )
        with app.app_context():
            status = WhatsAppService.get_status()
            assert status["pair_code"] == "ABCD-1234"


class TestSending:
    def test_send_message_serialized_and_uses_jid(self, app):
        mock_client = MagicMock()
        WhatsAppService._client = mock_client
        WhatsAppService._connected = True

        result = WhatsAppService.send_message("+90 555-111-22-33", "Merhaba")
        assert result["success"] is True
        jid = mock_client.send_message.call_args.args[0]
        assert jid.User == "905551112233"

    def test_send_makbuz_message_sends_text_and_pdf(self, app):
        mock_client = MagicMock()
        WhatsAppService._client = mock_client
        WhatsAppService._connected = True

        makbuz = MagicMock()
        makbuz.party.name = "Dr. Test"
        makbuz.party.phone = "+905551112233"
        makbuz.party.id = 7
        makbuz.month = 6
        makbuz.year = 2026
        makbuz.work_order_count = 3
        makbuz.subtotal = 1000.0
        makbuz.vat_applied = False
        makbuz.grand_total = 1000.0

        result = WhatsAppService.send_makbuz_message(makbuz, b"%PDF-fake")
        assert result["success"] is True
        mock_client.send_message.assert_called_once()
        mock_client.send_document.assert_called_once()
        doc_kwargs = mock_client.send_document.call_args.kwargs
        assert doc_kwargs["filename"] == "makbuz_2026_06_7.pdf"
        assert doc_kwargs["mimetype"] == "application/pdf"
