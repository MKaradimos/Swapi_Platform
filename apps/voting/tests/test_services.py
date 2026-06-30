import pytest
from rest_framework.exceptions import ValidationError

from apps.voting.models import Vote
from apps.voting.services import cast_vote, has_user_voted, vote_count_for

pytestmark = pytest.mark.django_db


class TestCastVote:
    def test_first_call_creates_vote(self, user, character):
        vote, created = cast_vote(user, character)
        assert created is True
        assert vote is not None
        assert Vote.objects.count() == 1

    def test_second_call_removes_vote(self, user, character):
        cast_vote(user, character)
        vote, created = cast_vote(user, character)
        assert created is False
        assert vote is None
        assert Vote.objects.count() == 0

    def test_rejects_non_votable_model(self, user):
        class NotVotable:
            pk = 1

        with pytest.raises(ValidationError):
            cast_vote(user, NotVotable())

    def test_votes_for_different_items_are_independent(self, user, character, film):
        cast_vote(user, character)
        cast_vote(user, film)
        assert Vote.objects.filter(user=user).count() == 2

    def test_unique_constraint_prevents_db_level_duplicate(self, user, character):
        """
        Sanity check that the DB constraint itself (not just service-level
        logic) prevents duplicate votes, in case service logic is bypassed.
        """
        from django.contrib.contenttypes.models import ContentType
        from django.db import IntegrityError, transaction

        ct = ContentType.objects.get_for_model(character)
        Vote.objects.create(user=user, content_type=ct, object_id=character.pk)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Vote.objects.create(user=user, content_type=ct, object_id=character.pk)


class TestVoteCountFor:
    def test_zero_when_no_votes(self, character):
        assert vote_count_for(character) == 0

    def test_counts_votes_across_multiple_users(self, character, user, other_user):
        cast_vote(user, character)
        cast_vote(other_user, character)
        assert vote_count_for(character) == 2

    def test_does_not_count_votes_for_other_items(self, character, film, user):
        cast_vote(user, character)
        assert vote_count_for(film) == 0


class TestCastVoteRaceCondition:
    """
    Covers the `except IntegrityError` branch in cast_vote(): two
    concurrent requests both pass the "does a vote already exist?" check
    (neither sees the other's row yet), then both attempt to create one —
    only one INSERT can win due to the unique_together constraint, and
    the loser must recover gracefully rather than 500.

    Reproducing a *real* race deterministically in a single-threaded test
    isn't practical, so this mocks Vote.objects.create to simulate the
    losing side of that race: the mock both inserts the "winning"
    concurrent vote for real (so there's something genuine for the
    recovery path to find and clean up) and raises IntegrityError, mirroring
    exactly what Vote.objects.create() would do if a concurrent request's
    row already existed when this one's INSERT hit the database.
    """

    def test_integrity_error_during_create_is_recovered_as_unvote(self, user, character):
        from unittest.mock import patch

        from django.contrib.contenttypes.models import ContentType
        from django.db import IntegrityError

        content_type = ContentType.objects.get_for_model(character)
        real_create = Vote.objects.create

        def simulate_concurrent_winner(*args, **kwargs):
            # A concurrent request "wins" the race and inserts first.
            real_create(user=user, content_type=content_type, object_id=character.pk)
            raise IntegrityError("duplicate key value violates unique constraint")

        with patch.object(Vote.objects, "create", side_effect=simulate_concurrent_winner):
            vote, created = cast_vote(user, character)

        assert vote is None
        assert created is False
        # The recovery path's cleanup delete() must have removed the row
        # the "concurrent winner" inserted — not leave it dangling, and
        # not raise the IntegrityError up to the caller.
        assert (
            Vote.objects.filter(
                user=user, content_type=content_type, object_id=character.pk
            ).count()
            == 0
        )

    def test_integrity_error_recovery_does_not_affect_other_users_votes(
        self, user, other_user, character
    ):
        """
        The recovery cleanup must be scoped to the specific (user,
        content_type, object_id) tuple that raced — not accidentally wipe
        other users' votes for the same item.
        """
        from unittest.mock import patch

        from django.contrib.contenttypes.models import ContentType
        from django.db import IntegrityError

        cast_vote(other_user, character)  # unrelated, pre-existing vote
        content_type = ContentType.objects.get_for_model(character)
        real_create = Vote.objects.create

        def simulate_concurrent_winner(*args, **kwargs):
            real_create(user=user, content_type=content_type, object_id=character.pk)
            raise IntegrityError("duplicate key value violates unique constraint")

        with patch.object(Vote.objects, "create", side_effect=simulate_concurrent_winner):
            cast_vote(user, character)

        assert has_user_voted(other_user, character) is True


class TestHasUserVoted:
    def test_false_for_anonymous_user(self, character):
        from django.contrib.auth.models import AnonymousUser

        assert has_user_voted(AnonymousUser(), character) is False

    def test_false_before_voting(self, user, character):
        assert has_user_voted(user, character) is False

    def test_true_after_voting(self, user, character):
        cast_vote(user, character)
        assert has_user_voted(user, character) is True

    def test_false_after_unvoting(self, user, character):
        cast_vote(user, character)
        cast_vote(user, character)  # toggles off
        assert has_user_voted(user, character) is False
