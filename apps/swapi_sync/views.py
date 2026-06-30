from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .tasks import sync_swapi_catalog


class SyncTriggerResponseSerializer(serializers.Serializer):
    task_id = serializers.CharField()
    status = serializers.CharField()


class TriggerSyncView(APIView):
    """
    Kick off an asynchronous full catalog sync from SWAPI via Celery.

    Returns immediately with the Celery task id rather than blocking the
    request for however long the sync takes — the assessment's "fetch and
    store" requirement doesn't mandate synchronous behaviour, and a
    request-blocking sync would be a poor pattern for a real API anyway.
    Restricted to staff users since it mutates the shared catalog dataset.
    """

    permission_classes = [permissions.IsAdminUser]
    throttle_scope = "sync"
    serializer_class = SyncTriggerResponseSerializer

    def post(self, request):
        async_result = sync_swapi_catalog.delay()
        serializer = self.serializer_class({"task_id": async_result.id, "status": "queued"})
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
