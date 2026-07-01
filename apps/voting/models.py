from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.common.models import TimeStampedModel


class Vote(TimeStampedModel):
    """User vote for a catalog item via GenericForeignKey (one vote per user per item)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="votes"
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "content_type", "object_id"],
                name="unique_vote_per_user_per_item",
            )
        ]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} -> {self.content_object}"
