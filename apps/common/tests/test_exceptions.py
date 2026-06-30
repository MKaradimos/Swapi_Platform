import pytest
from django.urls import reverse

from apps.common.exceptions import (
    ExternalAPIError,
    ServiceUnavailableError,
    custom_exception_handler,
)

pytestmark = pytest.mark.django_db


class TestExceptionResponseShape:
    """
    Every error response from the API should follow the same
    {"error": {"code": ..., "message": ...}} shape, regardless of which
    underlying DRF/Django exception produced it. These tests hit real
    endpoints to verify the handler is actually wired in end-to-end,
    rather than unit-testing the handler function in isolation.
    """

    def test_404_has_consistent_shape(self, api_client):
        response = api_client.get(reverse("character-detail", args=[99999]))
        assert response.status_code == 404
        assert response.data["error"]["code"] == "not_found"
        assert "message" in response.data["error"]

    def test_401_has_consistent_shape(self, api_client, character):
        response = api_client.post(reverse("character-vote", args=[character.id]))
        assert response.status_code == 401
        assert response.data["error"]["code"] == "not_authenticated"

    def test_validation_error_includes_details(self, api_client):
        response = api_client.post(
            reverse("accounts:register"),
            {
                "username": "",  # invalid: blank
                "email": "not-an-email",
                "password": "x",
                "password_confirm": "y",
            },
        )
        assert response.status_code == 400
        assert response.data["error"]["code"] == "validation_error"
        assert "details" in response.data["error"]

    def test_405_has_consistent_shape(self, auth_client):
        response = auth_client.delete(reverse("film-list"))
        assert response.status_code == 405
        assert response.data["error"]["code"] == "method_not_allowed"


class TestCustomExceptionHandlerDirectly:
    """
    Unit tests calling custom_exception_handler() directly for failure
    modes that are awkward to trigger through a real view (upstream
    service errors, truly unhandled exceptions) but still need to be
    verified to produce the documented response shape.
    """

    def test_service_unavailable_returns_503(self):
        response = custom_exception_handler(
            ServiceUnavailableError("SWAPI unreachable"), {"view": None}
        )
        assert response.status_code == 503
        assert response.data["error"]["code"] == "service_unavailable"
        assert response.data["error"]["message"] == "SWAPI unreachable"

    def test_service_unavailable_with_no_message_uses_default(self):
        response = custom_exception_handler(ServiceUnavailableError(), {"view": None})
        assert response.data["error"]["message"] == "Upstream service unavailable."

    def test_external_api_error_returns_502(self):
        response = custom_exception_handler(ExternalAPIError("SWAPI returned 500"), {"view": None})
        assert response.status_code == 502
        assert response.data["error"]["code"] == "external_api_error"

    def test_truly_unhandled_exception_returns_generic_500(self):
        response = custom_exception_handler(RuntimeError("boom"), {"view": None})
        assert response.status_code == 500
        assert response.data["error"]["code"] == "internal_error"
        assert "unexpected error" in response.data["error"]["message"].lower()
