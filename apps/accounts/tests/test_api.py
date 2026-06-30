from unittest import mock

import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.models import User

pytestmark = pytest.mark.django_db


class TestRegisterEndpoint:
    def test_register_creates_user_and_returns_tokens(self, api_client):
        response = api_client.post(
            reverse("accounts:register"),
            {
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "StrongPass123!",
                "password_confirm": "StrongPass123!",
            },
        )
        assert response.status_code == 201
        assert User.objects.filter(username="newuser").exists()
        assert "access" in response.data["tokens"]
        assert "refresh" in response.data["tokens"]

    def test_register_rejects_mismatched_passwords(self, api_client):
        response = api_client.post(
            reverse("accounts:register"),
            {
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "StrongPass123!",
                "password_confirm": "DifferentPass456!",
            },
        )
        assert response.status_code == 400
        assert response.data["error"]["code"] == "validation_error"

    def test_register_rejects_weak_password(self, api_client):
        response = api_client.post(
            reverse("accounts:register"),
            {
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "12345678",
                "password_confirm": "12345678",
            },
        )
        assert response.status_code == 400

    def test_register_rejects_duplicate_username(self, api_client, user):
        response = api_client.post(
            reverse("accounts:register"),
            {
                "username": user.username,
                "email": "different@example.com",
                "password": "StrongPass123!",
                "password_confirm": "StrongPass123!",
            },
        )
        assert response.status_code == 400

    def test_register_rejects_duplicate_email(self, api_client, user):
        response = api_client.post(
            reverse("accounts:register"),
            {
                "username": "differentname",
                "email": user.email,
                "password": "StrongPass123!",
                "password_confirm": "StrongPass123!",
            },
        )
        assert response.status_code == 400


class TestLoginEndpoint:
    def test_login_with_valid_credentials(self, api_client, user):
        response = api_client.post(
            reverse("accounts:login"),
            {
                "username": user.username,
                "password": "StrongPass123!",
            },
        )
        assert response.status_code == 200
        assert "access" in response.data
        assert "refresh" in response.data

    def test_login_with_invalid_password(self, api_client, user):
        response = api_client.post(
            reverse("accounts:login"),
            {
                "username": user.username,
                "password": "WrongPassword",
            },
        )
        assert response.status_code == 401

    def test_token_refresh(self, api_client, user):
        login_response = api_client.post(
            reverse("accounts:login"),
            {
                "username": user.username,
                "password": "StrongPass123!",
            },
        )
        refresh_token = login_response.data["refresh"]
        response = api_client.post(reverse("accounts:token_refresh"), {"refresh": refresh_token})
        assert response.status_code == 200
        assert "access" in response.data


class TestAuthThrottling:
    """
    Login and register share the "auth" throttle scope so brute-force
    credential guessing / mass account creation is rate-limited.

    DRF caches REST_FRAMEWORK settings on import into its own
    `api_settings` singleton, so Django's `override_settings` does *not*
    reliably affect already-instantiated throttle classes (a well-known
    DRF testing gotcha: see encode/django-rest-framework#2466). The
    reliable way to test throttling is to patch the throttle class's
    resolved rate table directly, which is what `_tight_auth_throttle`
    below does.
    """

    @pytest.fixture(autouse=True)
    def _clear_throttle_cache(self):
        cache.clear()
        yield
        cache.clear()

    @staticmethod
    def _tight_auth_throttle():
        return mock.patch.object(
            ScopedRateThrottle,
            "THROTTLE_RATES",
            {"sync": "1000/min", "vote": "1000/min", "auth": "2/min"},
        )

    def test_login_is_throttled_after_limit_exceeded(self, api_client, user):
        credentials = {"username": user.username, "password": "WrongPassword"}

        with self._tight_auth_throttle():
            first = api_client.post(reverse("accounts:login"), credentials)
            second = api_client.post(reverse("accounts:login"), credentials)
            third = api_client.post(reverse("accounts:login"), credentials)

        assert first.status_code == 401  # wrong password, but not yet throttled
        assert second.status_code == 401
        assert third.status_code == 429  # 3rd request within the window is throttled
        assert third.data["error"]["code"] == "throttled"

    def test_register_is_throttled_after_limit_exceeded(self, api_client):
        def attempt(suffix):
            return api_client.post(
                reverse("accounts:register"),
                {
                    "username": f"throttleuser{suffix}",
                    "email": f"throttle{suffix}@example.com",
                    "password": "StrongPass123!",
                    "password_confirm": "StrongPass123!",
                },
            )

        with self._tight_auth_throttle():
            first = attempt(1)
            second = attempt(2)
            third = attempt(3)

        assert first.status_code == 201
        assert second.status_code == 201
        assert third.status_code == 429

    def test_login_and_register_share_the_same_throttle_bucket(self, api_client, user):
        """
        Both views use throttle_scope="auth", so attempts against either
        endpoint count against the same per-IP limit — this is what
        prevents someone from dodging a login throttle by hammering
        register instead, or vice versa.
        """
        with self._tight_auth_throttle():
            api_client.post(
                reverse("accounts:login"), {"username": user.username, "password": "wrong"}
            )
            api_client.post(
                reverse("accounts:login"), {"username": user.username, "password": "wrong"}
            )
            # third request, against the *other* auth endpoint, should still be throttled
            response = api_client.post(
                reverse("accounts:register"),
                {
                    "username": "someoneelse",
                    "email": "someoneelse@example.com",
                    "password": "StrongPass123!",
                    "password_confirm": "StrongPass123!",
                },
            )
        assert response.status_code == 429

    def test_me_endpoint_is_not_subject_to_auth_throttle_scope(self, auth_client, user):
        """
        Sanity check that the "auth" scope only applies where explicitly
        set (login/register) and doesn't leak onto unrelated authenticated
        endpoints via DEFAULT_THROTTLE_CLASSES.
        """
        with self._tight_auth_throttle():
            for _ in range(5):
                response = auth_client.get(reverse("accounts:me"))
                assert response.status_code == 200


class TestMeEndpoint:
    def test_me_requires_authentication(self, api_client):
        response = api_client.get(reverse("accounts:me"))
        assert response.status_code == 401

    def test_me_returns_current_user(self, auth_client, user):
        response = auth_client.get(reverse("accounts:me"))
        assert response.status_code == 200
        assert response.data["username"] == user.username
        assert response.data["email"] == user.email
