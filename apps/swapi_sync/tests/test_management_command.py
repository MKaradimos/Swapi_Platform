from io import StringIO

import pytest
import responses
from django.core.management import call_command

from apps.catalog.models import Film

pytestmark = pytest.mark.django_db


class TestSyncSwapiManagementCommand:
    @responses.activate
    def test_command_reports_synced_counts(self, swapi_film_payload):
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

        out = StringIO()
        call_command("sync_swapi", stdout=out)

        output = out.getvalue()
        assert "Films synced: 1" in output
        assert "Sync completed with no errors" in output
        assert Film.objects.count() == 1

    @responses.activate
    def test_command_reports_errors_without_raising(self):
        bad_payload = {"title": "Broken"}  # missing required 'url'
        responses.add(
            responses.GET,
            "https://swapi.dev/api/films/",
            json={"count": 1, "next": None, "previous": None, "results": [bad_payload]},
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

        out = StringIO()
        call_command("sync_swapi", stdout=out)

        output = out.getvalue()
        assert "failed to sync" in output
