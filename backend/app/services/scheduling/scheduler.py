"""APScheduler-backed callback scheduling.

FREE and in-process - no Redis, no Celery worker. Swap AsyncIOScheduler for a
Celery beat setup later without touching the callers: they only use
`schedule_callback_job` / `cancel_callback_job`.
"""
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

from app.core.config import settings
from app.core.events import bus
from app.core.logging import get_logger
from app.utils.timeutil import IST, UTC, as_utc, human_ist, now_utc

log = get_logger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone=str(UTC))
    return _scheduler


def start_scheduler() -> None:
    if not settings.SCHEDULER_ENABLED:
        log.info("Scheduler disabled by config")
        return
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        scheduler.add_job(
            sweep_due_callbacks,
            "interval",
            minutes=5,
            id="callback_sweeper",
            replace_existing=True,
        )
        log.info("APScheduler started (timezone=%s, display=%s)", UTC, settings.TIMEZONE)


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None


def job_id(callback_id: int) -> str:
    return f"callback:{callback_id}"


def schedule_callback_job(callback_id: int, run_at: datetime) -> None:
    """Fire a due-notification at `run_at` (any tz; normalised to UTC)."""
    if not settings.SCHEDULER_ENABLED:
        return
    scheduler = get_scheduler()
    if not scheduler.running:
        start_scheduler()

    run_at_utc = as_utc(run_at) or now_utc()
    if run_at_utc <= now_utc():
        run_at_utc = now_utc() + timedelta(seconds=5)

    scheduler.add_job(
        fire_callback,
        trigger=DateTrigger(run_date=run_at_utc),
        args=[callback_id],
        id=job_id(callback_id),
        replace_existing=True,
        misfire_grace_time=3600,
    )
    log.info("Callback #%s scheduled for %s IST", callback_id, human_ist(run_at_utc))


def cancel_callback_job(callback_id: int) -> None:
    scheduler = get_scheduler()
    try:
        scheduler.remove_job(job_id(callback_id))
    except Exception:  # noqa: BLE001 - job may already have fired
        pass


async def fire_callback(callback_id: int) -> None:
    """Runs when a scheduled callback comes due."""
    from app.db.session import session_scope
    from app.models import Callback, Customer

    db = session_scope()
    try:
        callback = db.get(Callback, callback_id)
        if not callback or callback.status not in ("scheduled", "due"):
            return
        customer = db.get(Customer, callback.customer_id)
        callback.status = "due"
        db.commit()

        payload: Dict[str, Any] = {
            "callback_id": callback.id,
            "customer_id": callback.customer_id,
            "customer_name": customer.name if customer else None,
            "phone_number": customer.phone_number if customer else None,
            "scheduled_time": human_ist(callback.scheduled_time),
            "original_text": callback.original_text,
            "interpretation": callback.interpretation,
            "message": f"Callback due for {customer.name if customer else 'customer'}",
        }
        await bus.broadcast("callback.due", payload, call_id=callback.call_id)
        log.info("Callback #%s is now due", callback_id)
    finally:
        db.close()


async def sweep_due_callbacks() -> None:
    """Safety net: catches callbacks that came due while the app was down."""
    from app.db.session import session_scope
    from app.models import Callback

    db = session_scope()
    try:
        pending = (
            db.query(Callback)
            .filter(Callback.status == "scheduled", Callback.scheduled_time <= datetime.now(UTC))
            .all()
        )
        for callback in pending:
            await fire_callback(callback.id)
    except Exception as exc:  # noqa: BLE001
        log.warning("Callback sweep failed: %s", exc)
    finally:
        db.close()


def rehydrate_jobs() -> None:
    """Re-arm scheduled callbacks after a restart (jobs live in memory)."""
    from app.db.session import session_scope
    from app.models import Callback

    db = session_scope()
    try:
        upcoming = (
            db.query(Callback)
            .filter(Callback.status == "scheduled", Callback.scheduled_time > datetime.now(UTC))
            .all()
        )
        for callback in upcoming:
            schedule_callback_job(callback.id, as_utc(callback.scheduled_time))
        if upcoming:
            log.info("Re-armed %d pending callback(s)", len(upcoming))
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not rehydrate callback jobs: %s", exc)
    finally:
        db.close()
