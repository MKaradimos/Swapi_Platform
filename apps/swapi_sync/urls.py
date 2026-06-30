from django.urls import path

from .views import TriggerSyncView

app_name = "swapi_sync"

urlpatterns = [
    path("trigger/", TriggerSyncView.as_view(), name="trigger"),
]
