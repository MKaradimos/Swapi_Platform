from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.common.models import TimeStampedModel


class Vote(TimeStampedModel):
    """
    A single user's vote for a favourite catalog item.

    Uses a GenericForeignKey rather than three separate FK columns
    (character/film/starship) or three separate Vote subclasses. This
    keeps voting logic, serializers, and permission checks in one place
    instead of tripled across entity types, at the cost of losing a
    database-level FK constraint on the target — acceptable here since
    the target is always validated against an allow-list of catalog
    models at the serializer/service layer (see services.py).

    The unique_together constraint is what actually enforces "one vote
    per user per item": a second vote attempt should toggle/remove the
    existing vote rather than create a duplicate row (see VotingService).
    """

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
