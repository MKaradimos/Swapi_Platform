"""
Service layer for voting.

Keeps the "what counts as a votable item" allow-list and the toggle
semantics (vote / un-vote on repeated POST) out of the view layer, so
views stay thin and this logic is independently testable.
"""

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
    """
    Toggle a user's vote on `instance`.

    Returns (vote_or_none, created):
      - (Vote, True)  -> a new vote was created
      - (None, False) -> an existing vote was found and removed (un-vote)

    Race-safety: two concurrent requests to vote for the same item by the
    same user will hit the unique_together constraint; the IntegrityError
    is caught and treated as "someone else just created it", so we
    re-fetch and remove it consistently rather than erroring out.
    """
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
        # Lost a race to a concurrent request creating the same vote;
        # treat it the same as "vote already existed" and remove it.
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
