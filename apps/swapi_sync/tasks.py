"""Celery tasks for SWAPI sync with exponential backoff retry."""

import logging

from celery import shared_task

from apps.common.exceptions import ServiceUnavailableError

from .services.sync import run_full_sync

logger = logging.getLogger("apps.swapi_sync.tasks")


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(ServiceUnavailableError,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def sync_swapi_catalog(self):
    """Full catalog sync: films → starships → characters, with per-record error capture."""
    logger.info("sync_swapi_catalog task started (attempt %s)", self.request.retries + 1)
    result = run_full_sync()
    if result.errors:
        logger.warning(
            "sync_swapi_catalog finished with %s record-level errors", len(result.errors)
        )
    return result.as_dict()
