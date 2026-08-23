"""
APScheduler-based relay for the Transactional Outbox Pattern.

The relay runs as a background thread inside the Gunicorn/uvicorn process.
Every 300 ms it opens a DB session, calls `publish_pending`, then closes it.

Lifecycle
─────────
`start()` is called from main.py's FastAPI lifespan on application startup.
`stop()` is called from the lifespan on shutdown to drain the scheduler
cleanly before the process exits.

Why APScheduler (not a separate process)?
- No extra infrastructure: no Celery, no Redis, no separate worker process.
- The outbox only needs to flush ~every 300 ms; a lightweight thread is
  perfectly sufficient for this throughput.
- For very high event volumes, move the relay to a dedicated worker process
  or use pg_notify to trigger it immediately.

Thread safety
─────────────
APScheduler's BackgroundScheduler runs the job in a single background thread.
Each job invocation creates its own DB session and closes it when done —
no shared session state between invocations.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.db import SessionLocal
from app.services.events import publish_pending

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler()


def _relay_tick() -> None:
    """Open a short-lived session, flush pending events, close the session."""
    db = SessionLocal()
    try:
        publish_pending(db)
    except Exception:
        logger.exception("Outbox relay tick failed")
    finally:
        db.close()


def start() -> None:
    """Start the background relay.  Called once at application startup."""
    if _scheduler.running:
        return
    _scheduler.add_job(
        _relay_tick,
        trigger="interval",
        seconds=0.3,  # ~300 ms between ticks
        id="outbox_relay",
        max_instances=1,  # prevent overlap if a tick takes longer than 300 ms
        coalesce=True,
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Outbox relay started (interval=300ms)")


def stop() -> None:
    """Stop the background relay gracefully.  Called at application shutdown."""
    if _scheduler.running:
        _scheduler.shutdown(wait=True)
        logger.info("Outbox relay stopped")
