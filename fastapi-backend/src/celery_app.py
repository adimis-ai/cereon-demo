from __future__ import annotations

import sys
import logging
from pathlib import Path
from celery import Celery
from typing import Any, Dict, List, Type


from settings import get_settings

s = get_settings()
logging.basicConfig(
    level=s.log_level.upper(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("celery")


def create_celery(settings) -> Celery:
    """
    Factory to create a configured Celery instance.

    Keeps config colocated and testable. No side effects beyond app construction.
    """
    app = Celery(
        main=settings.app_name,
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
    )
    app.conf.update(
        task_default_queue=settings.celery_task_default_queue,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        worker_hijack_root_logger=False,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        broker_heartbeat=30,
        broker_connection_retry_on_startup=True,
        result_extended=True,
        timezone="UTC",
        worker_send_task_events=True,
        task_send_sent_event=True,
        # Beat schedule configuration
        beat_schedule={},
        beat_scheduler="celery.beat:PersistentScheduler",
        beat_schedule_filename="celerybeat-schedule",
    )
    return app


celery_app: Celery = create_celery(s)


@celery_app.task(name="tasks.ping")
def ping(payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Trivial health task to verify worker reachability and queue wiring.
    """
    return {"ok": True, "payload": payload or {}, "worker": s.app_name}
