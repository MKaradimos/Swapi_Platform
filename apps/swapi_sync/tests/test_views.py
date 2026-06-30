import pytest
import responses
from django.urls import reverse

pytestmark = pytest.mark.django_db


class TestTriggerSyncView:
    def test_requires_authentication(self, api_client):
        response = api_client.post(reverse("swapi_sync:trigger"))
        assert response.status_code == 401

    def test_requires_admin_permission(self, auth_client):
        """A regular authenticated (non-staff) user must not be able to trigger a sync."""
        response = auth_client.post(reverse("swapi_sync:trigger"))
        assert response.status_code == 403

    @responses.activate
    def test_admin_can_trigger_sync(self, admin_client_jwt):
        # CELERY_TASK_ALWAYS_EAGER means .delay() runs synchronously, so
        # the underlying SWAPI calls the task makes need to be mocked too.
        for resource in ("films", "starships", "people"):
            responses.add(
                responses.GET,
                f"https://swapi.dev/api/{resource}/",
                json={"count": 0, "next": None, "previous": None, "results": []},
                status=200,
            )
        response = admin_client_jwt.post(reverse("swapi_sync:trigger"))
        assert response.status_code == 202
        assert "task_id" in response.data
        assert response.data["status"] == "queued"
