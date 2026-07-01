"""HTTP client for SWAPI: retries, pagination, and error translation."""

import logging
import time
from typing import Iterator
from urllib.parse import urljoin

import requests
from django.conf import settings

from apps.common.exceptions import ExternalAPIError, ServiceUnavailableError

logger = logging.getLogger("apps.swapi_sync.client")


class SwapiClient:
    """Small, retrying HTTP client for the Star Wars API."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: int | None = None,
        max_retries: int | None = None,
        backoff_seconds: int | None = None,
        session: requests.Session | None = None,
    ):
        self.base_url = (base_url or settings.SWAPI_BASE_URL).rstrip("/") + "/"
        self.timeout = timeout or settings.SWAPI_REQUEST_TIMEOUT
        self.max_retries = max_retries if max_retries is not None else settings.SWAPI_MAX_RETRIES
        self.backoff_seconds = (
            backoff_seconds if backoff_seconds is not None else settings.SWAPI_RETRY_BACKOFF_SECONDS
        )
        self.session = session or requests.Session()

    def _get(self, url: str) -> dict:
        """GET with retry on timeouts, connection errors, and 5xx responses."""
        last_exc: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.get(url, timeout=self.timeout)
            except requests.Timeout as exc:
                last_exc = exc
                logger.warning(
                    "SWAPI request timed out (attempt %s/%s): %s", attempt, self.max_retries, url
                )
            except requests.ConnectionError as exc:
                last_exc = exc
                logger.warning(
                    "SWAPI connection error (attempt %s/%s): %s", attempt, self.max_retries, url
                )
            else:
                if response.status_code == 404:
                    raise ExternalAPIError(f"SWAPI resource not found: {url}")
                if 500 <= response.status_code < 600:
                    last_exc = ExternalAPIError(f"SWAPI returned {response.status_code} for {url}")
                    logger.warning(
                        "SWAPI server error %s (attempt %s/%s): %s",
                        response.status_code,
                        attempt,
                        self.max_retries,
                        url,
                    )
                elif response.status_code >= 400:
                    raise ExternalAPIError(
                        f"SWAPI returned {response.status_code} for {url}: {response.text[:200]}"
                    )
                else:
                    try:
                        return response.json()
                    except ValueError as exc:
                        raise ExternalAPIError(
                            f"SWAPI returned non-JSON response for {url}"
                        ) from exc

            if attempt < self.max_retries:
                time.sleep(self.backoff_seconds * attempt)  # linear backoff

        raise ServiceUnavailableError(
            f"SWAPI unreachable after {self.max_retries} attempts: {url}"
        ) from last_exc

    def _paginate(self, resource: str) -> Iterator[dict]:
        """Yield every result across all pages of a paginated SWAPI list endpoint."""
        url = urljoin(self.base_url, f"{resource}/")
        while url:
            payload = self._get(url)
            for result in payload.get("results", []):
                yield result
            url = payload.get("next")

    def iter_people(self) -> Iterator[dict]:
        return self._paginate("people")

    def iter_films(self) -> Iterator[dict]:
        return self._paginate("films")

    def iter_starships(self) -> Iterator[dict]:
        return self._paginate("starships")

    def get_resource(self, url: str) -> dict:
        """Fetch a single SWAPI resource by its full URL (used for cross-references)."""
        return self._get(url)
