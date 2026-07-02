"""Custom exception handler: normalises all API errors to a consistent JSON shape."""

import logging

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions as drf_exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_default_exception_handler

logger = logging.getLogger("apps.common.exceptions")


class ServiceUnavailableError(Exception):
    """Raised when an upstream dependency (e.g. SWAPI) cannot be reached."""


class ExternalAPIError(Exception):
    """Raised when an upstream API returns an unexpected/error response."""


def _error_code_for(exc):
    """Map an exception instance to a short machine-readable error code."""
    mapping = {
        drf_exceptions.ValidationError: "validation_error",
        drf_exceptions.AuthenticationFailed: "authentication_failed",
        drf_exceptions.NotAuthenticated: "not_authenticated",
        drf_exceptions.PermissionDenied: "permission_denied",
        drf_exceptions.NotFound: "not_found",
        drf_exceptions.MethodNotAllowed: "method_not_allowed",
        drf_exceptions.Throttled: "throttled",
        drf_exceptions.ParseError: "parse_error",
        drf_exceptions.UnsupportedMediaType: "unsupported_media_type",
        Http404: "not_found",
        PermissionDenied: "permission_denied",
        ServiceUnavailableError: "service_unavailable",
        ExternalAPIError: "external_api_error",
    }
    for exc_type, code in mapping.items():
        if isinstance(exc, exc_type):
            return code
    return "internal_error"


def custom_exception_handler(exc, context):
    """Normalise all API errors to a consistent JSON shape."""
    if isinstance(exc, ServiceUnavailableError):
        response = Response(status=503)
        response.data = {"detail": str(exc) or "Upstream service unavailable."}
    elif isinstance(exc, ExternalAPIError):
        response = Response(status=502)
        response.data = {"detail": str(exc) or "Upstream service returned an error."}
    else:
        response = drf_default_exception_handler(exc, context)

    if response is None:
        # Unhandled exception (bug, DB error, etc). Log full traceback,
        # never leak internals to the client.
        logger.exception("Unhandled exception in view: %s", context.get("view"))
        return Response(
            {
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred. Please try again later.",
                }
            },
            status=500,
        )

    code = _error_code_for(exc)
    detail = response.data

    if isinstance(detail, dict) and "detail" in detail and len(detail) == 1:
        message = str(detail["detail"])
        details = None
    elif isinstance(detail, (dict, list)):
        message = (
            "One or more fields failed validation."
            if code == "validation_error"
            else "Request failed."
        )
        details = detail
    else:
        message = str(detail)
        details = None

    payload = {"error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details

    response.data = payload
    return response
