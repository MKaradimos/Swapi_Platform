"""
Celery tasks for SWAPI synchronisation.

The task body stays thin on purpose: all real logic lives in
services/sync.py, which is plain Python with no Celery dependency and is
directly unit-testable. The task adds the operational concerns Celery is
good at — retries with exponential backoff when SWAPI is transiently
unreachable, and structured logging of the outcome.
"""

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
    """
    Full catalog sync from SWAPI (films -> starships -> characters).

    Automatically retried with exponential backoff if SWAPI is
    unreachable; individual record-level failures are captured in the
    result rather than aborting the whole run.
    """
    logger.info("sync_swapi_catalog task started (attempt %s)", self.request.retries + 1)
    result = run_full_sync()
    if result.errors:
        logger.warning(
            "sync_swapi_catalog finished with %s record-level errors", len(result.errors)
        )
    return result.as_dict()
