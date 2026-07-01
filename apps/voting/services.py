"""Voting service: toggle vote/un-vote logic and allow-list validation."""

from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError
from rest_framework.exceptions import ValidationError

from apps.catalog.models import Character, Film, Starship

from .models import Vote

VOTABLE_MODELS = (Character, Film, Starship)


def _validate_votable(instance) -> None:
    if not isinstance(instance, VOTABLE_MODELS):
        raise ValidationError(f"{type(instance).__name__} is not a votable resource.")


def cast_vote(user, instance) -> tuple[Vote | None, bool]:
    """Toggle vote on instance. Returns (vote, True) on create or (None, False) on delete."""
    _validate_votable(instance)
    content_type = ContentType.objects.get_for_model(instance)

    existing = Vote.objects.filter(
        user=user, content_type=content_type, object_id=instance.pk
    ).first()

    if existing:
        existing.delete()
        return None, False

    try:
        vote = Vote.objects.create(user=user, content_type=content_type, object_id=instance.pk)
        return vote, True
    except IntegrityError:
        # Concurrent request created the same vote first; treat as un-vote.
        Vote.objects.filter(user=user, content_type=content_type, object_id=instance.pk).delete()
        return None, False


def vote_count_for(instance) -> int:
    content_type = ContentType.objects.get_for_model(instance)
    return Vote.objects.filter(content_type=content_type, object_id=instance.pk).count()


def has_user_voted(user, instance) -> bool:
    if not user or not user.is_authenticated:
        return False
    content_type = ContentType.objects.get_for_model(instance)
    return Vote.objects.filter(user=user, content_type=content_type, object_id=instance.pk).exists()
