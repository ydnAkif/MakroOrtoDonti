"""Ayın 1'inde çalışan makbuz arkaplan görevleri.

06:00 — bir önceki ayın makbuz taslaklarını oluşturur (KDV gerektiren
doktorlar makbuzlar ekranında elle işaretlenir; bu görev göndermez).
06:30 — "Otomatik gönderim" ayarı açıksa ve WhatsApp bağlıysa, önceki ayın
taslak makbuzlarını WhatsApp gönderim kuyruğuna verir.
"""

import logging
import os
from datetime import date, timedelta
from decimal import Decimal

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None

SETTINGS_KEY = "makbuz_auto_run_date"
AUTO_SEND_RUN_KEY = "makbuz_auto_send_run_date"
AUTO_SEND_TOGGLE_KEY = "whatsapp_auto_send_makbuz"


def _previous_month(today: date) -> tuple[int, int]:
    first_of_this_month = today.replace(day=1)
    last_day_of_prev_month = first_of_this_month - timedelta(days=1)
    return last_day_of_prev_month.year, last_day_of_prev_month.month


def _claim_todays_run(key: str = SETTINGS_KEY, description: str | None = None) -> bool:
    """Atomically mark today as run so only one process/worker executes the job."""
    from app.extensions import db
    from app.models.models import Settings

    today_str = date.today().isoformat()

    row = db.session.execute(
        db.select(Settings).where(Settings.key == key)
    ).scalar_one_or_none()
    if row is None:
        db.session.add(Settings(
            key=key, value="",
            description=description
            or "Otomatik makbuz taslağı üretiminin en son çalıştığı gün (YYYY-MM-DD)",
        ))
        db.session.commit()

    result = db.session.execute(
        db.update(Settings)
        .where(Settings.key == key, Settings.value != today_str)
        .values(value=today_str)
    )
    db.session.commit()
    return result.rowcount == 1


def auto_send_enabled() -> bool:
    """Read the auto-send toggle from Settings (default: off)."""
    from app.extensions import db
    from app.models.models import Settings

    value = db.session.execute(
        db.select(Settings.value).where(Settings.key == AUTO_SEND_TOGGLE_KEY)
    ).scalar_one_or_none()
    return value == "true"


def _generate_monthly_drafts(app) -> None:
    with app.app_context():
        today = date.today()
        if today.day != 1:
            return
        if not _claim_todays_run():
            return

        from app.extensions import db
        from app.models.models import Party, WorkOrder, Makbuz
        from app.routes.makbuzlar import _generate_makbuz
        from sqlalchemy import extract

        year, month = _previous_month(today)

        party_ids = db.session.execute(
            db.select(WorkOrder.party_id)
            .join(Party, WorkOrder.party_id == Party.id)
            .where(
                extract("year", WorkOrder.work_date) == year,
                extract("month", WorkOrder.work_date) == month,
                Party.is_active == True,
            )
            .distinct()
        ).scalars().all()

        created = 0
        for party_id in party_ids:
            existing = db.session.execute(
                db.select(Makbuz).where(
                    Makbuz.party_id == party_id, Makbuz.year == year, Makbuz.month == month
                )
            ).scalar_one_or_none()
            if existing:
                continue
            try:
                _generate_makbuz(party_id, year, month, vat_applied=False, vat_rate=Decimal("0"))
                db.session.commit()
                created += 1
            except ValueError:
                db.session.rollback()

        logger.info(
            "Otomatik makbuz taslağı üretimi tamamlandı: %s doktor, dönem %s-%02d",
            created, year, month,
        )


def _auto_send_monthly_makbuzlar(app) -> None:
    """Ayın 1'inde önceki ayın taslak makbuzlarını WhatsApp kuyruğuna verir."""
    with app.app_context():
        today = date.today()
        if today.day != 1:
            return
        if not auto_send_enabled():
            return

        from app.services.whatsapp_service import WhatsAppService

        if not WhatsAppService.get_status()["connected"]:
            logger.warning(
                "Otomatik makbuz gönderimi atlandı: WhatsApp bağlı değil. "
                "Taslaklar WhatsApp sayfasından elle gönderilebilir."
            )
            return

        from app.extensions import db
        from app.models.models import Makbuz, MakbuzSendLog, Party

        year, month = _previous_month(today)
        makbuz_ids = db.session.execute(
            db.select(Makbuz.id)
            .join(Party, Makbuz.party_id == Party.id)
            .where(
                Makbuz.year == year,
                Makbuz.month == month,
                Makbuz.status == Makbuz.STATUS_DRAFT,
                Party.is_active == True,
                Party.phone.isnot(None),
                Party.phone != "",
            )
        ).scalars().all()

        if not makbuz_ids:
            logger.info("Otomatik makbuz gönderimi: gönderilecek taslak yok (%s-%02d).", year, month)
            return

        if not _claim_todays_run(
            AUTO_SEND_RUN_KEY,
            "Otomatik makbuz gönderiminin en son çalıştığı gün (YYYY-MM-DD)",
        ):
            return

        from app.services.makbuz_send_queue import MakbuzSendQueue

        started, message = MakbuzSendQueue.start_batch(
            list(makbuz_ids), triggered_by=MakbuzSendLog.TRIGGER_SCHEDULER
        )
        if started:
            logger.info("Otomatik makbuz gönderimi başlatıldı: %s", message)
        else:
            logger.warning("Otomatik makbuz gönderimi başlatılamadı: %s", message)


def init_scheduler(app) -> None:
    """Start the background scheduler once per running process."""
    global _scheduler
    if _scheduler is not None:
        return
    if app.testing:
        return
    # Werkzeug'un debug reloader'ı ana süreci bir kez, alt süreci bir kez başlatır;
    # yalnızca gerçekten sunum yapan (child) süreçte başlat.
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        _generate_monthly_drafts,
        trigger="cron",
        hour=6,
        minute=0,
        args=[app],
        id="makbuz_monthly_drafts",
        replace_existing=True,
    )
    scheduler.add_job(
        _auto_send_monthly_makbuzlar,
        trigger="cron",
        hour=6,
        minute=30,
        args=[app],
        id="makbuz_monthly_auto_send",
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "Makbuz zamanlayıcısı başlatıldı (ayın 1'i: 06:00 taslaklar, "
        "06:30 otomatik gönderim — ayar açıksa)."
    )
