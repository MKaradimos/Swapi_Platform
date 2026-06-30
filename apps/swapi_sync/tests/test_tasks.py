import pytest
import responses

from apps.catalog.models import Film
from apps.swapi_sync.tasks import sync_swapi_catalog

pytestmark = pytest.mark.django_db


class TestSyncSwapiCatalogTask:
    @responses.activate
    def test_task_runs_full_sync_and_returns_summary(self, swapi_film_payload):
        responses.add(
            responses.GET,
            "https://swapi.dev/api/films/",
            json={"count": 1, "next": None, "previous": None, "results": [swapi_film_payload]},
            status=200,
        )
        responses.add(
            responses.GET,
            "https://swapi.dev/api/starships/",
            json={"count": 0, "next": None, "previous": None, "results": []},
            status=200,
        )
        responses.add(
            responses.GET,
            "https://swapi.dev/api/people/",
            json={"count": 0, "next": None, "previous": None, "results": []},
            status=200,
        )

        # CELERY_TASK_ALWAYS_EAGER (test settings) makes .delay() execute
        # synchronously in-process, so we can assert on both the return
        # value and the resulting DB state in one test.
        async_result = sync_swapi_catalog.delay()

        assert async_result.result["films_synced"] == 1
        assert async_result.result["total_synced"] == 1
        assert Film.objects.count() == 1
