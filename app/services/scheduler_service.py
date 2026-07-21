"""Ayın 1'inde, bir önceki ayın makbuz taslaklarını otomatik oluşturan arkaplan görevi.

KDV, gerektiği doktorlar için makbuzlar ekranında elle işaretlenir (bkz. plan);
bu görev yalnızca taslakları hazırlar, göndermez.
"""

import logging
import os
from datetime import date, timedelta
from decimal import Decimal

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None

SETTINGS_KEY = "makbuz_auto_run_date"


def _previous_month(today: date) -> tuple[int, int]:
    first_of_this_month = today.replace(day=1)
    last_day_of_prev_month = first_of_this_month - timedelta(days=1)
    return last_day_of_prev_month.year, last_day_of_prev_month.month


def _claim_todays_run() -> bool:
    """Atomically mark today as run so only one process/worker executes the job."""
    from app.extensions import db
    from app.models.models import Settings

    today_str = date.today().isoformat()

    row = db.session.execute(
        db.select(Settings).where(Settings.key == SETTINGS_KEY)
    ).scalar_one_or_none()
    if row is None:
        db.session.add(Settings(
            key=SETTINGS_KEY, value="",
            description="Otomatik makbuz taslağı üretiminin en son çalıştığı gün (YYYY-MM-DD)",
        ))
        db.session.commit()

    result = db.session.execute(
        db.update(Settings)
        .where(Settings.key == SETTINGS_KEY, Settings.value != today_str)
        .values(value=today_str)
    )
    db.session.commit()
    return result.rowcount == 1


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
    scheduler.start()
    _scheduler = scheduler
    logger.info("Makbuz zamanlayıcısı başlatıldı (her gün 06:00, ayın 1'inde çalışır).")
