import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.catalog.models import Character
from apps.voting.models import Vote
from apps.voting.services import cast_vote

pytestmark = pytest.mark.django_db


class TestCharacterListEndpoint:
    def test_list_unauthenticated_allowed(self, api_client, character):
        url = reverse("character-list")
        response = api_client.get(url)
        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["name"] == "Luke Skywalker"

    def test_list_includes_vote_count_and_is_voted_by_me(self, api_client, character):
        response = api_client.get(reverse("character-list"))
        body = response.data["results"][0]
        assert body["vote_count"] == 0
        assert body["is_voted_by_me"] is False

    def test_list_query_count_is_constant_regardless_of_page_size(
        self, auth_client, character, user, db
    ):
        """
        Regression test for an N+1 in vote_count/is_voted_by_me:
        annotated_vote_count is NULL (not 0) for items with zero votes
        because the underlying Subquery's GROUP BY returns no row for
        them. A naive `is not None` check in the serializer misreads that
        NULL as "annotation missing" and silently falls back to a
        per-row query for every unvoted item — the most common case.
        This mixes voted and unvoted characters in one list response and
        asserts the query count doesn't grow with the number of rows.
        """
        cast_vote(user, character)  # one voted character
        for i in range(10):  # ten more, unvoted
            Character.objects.create(
                swapi_url=f"https://swapi.dev/api/people/extra{i}/", name=f"Extra {i}"
            )

        with CaptureQueriesContext(connection) as ctx:
            response = auth_client.get(reverse("character-list"))
        assert response.status_code == 200
        assert response.data["count"] == 11

        # 5 fixed queries regardless of row count: auth user lookup,
        # pagination count, main list (with both annotations inline),
        # films prefetch, starships prefetch. If this regresses to
        # roughly 2 extra queries per character, the NULL-coalesce fix
        # has been lost.
        assert len(ctx.captured_queries) <= 6, (
            f"Expected a small constant query count, got {len(ctx.captured_queries)} "
            "queries for an 11-row list — looks like an N+1 regression."
        )

    def test_search_by_name(self, api_client, character, db):
        Character.objects.create(swapi_url="https://swapi.dev/api/people/4/", name="Darth Vader")
        response = api_client.get(reverse("character-list"), {"search": "Luke"})
        names = [r["name"] for r in response.data["results"]]
        assert names == ["Luke Skywalker"]

    def test_filter_by_gender(self, api_client, character, db):
        Character.objects.create(
            swapi_url="https://swapi.dev/api/people/5/", name="Leia Organa", gender="female"
        )
        response = api_client.get(reverse("character-list"), {"gender": "female"})
        names = [r["name"] for r in response.data["results"]]
        assert names == ["Leia Organa"]

    def test_pagination_page_size(self, api_client, db):
        for i in range(25):
            Character.objects.create(
                swapi_url=f"https://swapi.dev/api/people/{100 + i}/", name=f"Extra {i}"
            )
        response = api_client.get(reverse("character-list"))
        assert response.data["count"] == 25
        assert len(response.data["results"]) == 20  # PAGE_SIZE
        assert response.data["next"] is not None

    def test_ordering(self, api_client, db):
        Character.objects.create(swapi_url="https://swapi.dev/api/people/10/", name="Zorii")
        Character.objects.create(swapi_url="https://swapi.dev/api/people/11/", name="Anakin")
        response = api_client.get(reverse("character-list"), {"ordering": "name"})
        names = [r["name"] for r in response.data["results"]]
        assert names == ["Anakin", "Zorii"]


class TestCharacterDetailEndpoint:
    def test_retrieve_includes_nested_films_and_starships(self, api_client, character):
        url = reverse("character-detail", args=[character.id])
        response = api_client.get(url)
        assert response.status_code == 200
        assert response.data["name"] == "Luke Skywalker"
        assert response.data["films"] == ["A New Hope"]
        assert response.data["starships"] == ["X-wing"]

    def test_retrieve_nonexistent_returns_404(self, api_client):
        url = reverse("character-detail", args=[99999])
        response = api_client.get(url)
        assert response.status_code == 404
        assert response.data["error"]["code"] == "not_found"


class TestCharacterVoteEndpoint:
    def test_vote_requires_authentication(self, api_client, character):
        url = reverse("character-vote", args=[character.id])
        response = api_client.post(url)
        assert response.status_code == 401
        assert response.data["error"]["code"] == "not_authenticated"

    def test_authenticated_vote_creates_vote(self, auth_client, character, user):
        url = reverse("character-vote", args=[character.id])
        response = auth_client.post(url)
        assert response.status_code == 201
        assert response.data["voted"] is True
        assert response.data["item"]["vote_count"] == 1
        assert Vote.objects.filter(user=user).count() == 1

    def test_voting_twice_toggles_unvote(self, auth_client, character, user):
        url = reverse("character-vote", args=[character.id])
        auth_client.post(url)
        response = auth_client.post(url)
        assert response.status_code == 200
        assert response.data["voted"] is False
        assert response.data["item"]["vote_count"] == 0
        assert Vote.objects.filter(user=user).count() == 0

    def test_two_different_users_can_both_vote(self, api_client, character, user, other_user):
        url = reverse("character-vote", args=[character.id])

        api_client.force_authenticate(user=user)
        api_client.post(url)

        api_client.force_authenticate(user=other_user)
        response = api_client.post(url)

        assert response.data["item"]["vote_count"] == 2

    def test_is_voted_by_me_reflects_current_user_only(
        self, api_client, character, user, other_user
    ):
        vote_url = reverse("character-vote", args=[character.id])
        api_client.force_authenticate(user=user)
        api_client.post(vote_url)

        # other_user hasn't voted - should see is_voted_by_me: False
        api_client.force_authenticate(user=other_user)
        detail_response = api_client.get(reverse("character-detail", args=[character.id]))
        assert detail_response.data["is_voted_by_me"] is False

        # original voter should see True
        api_client.force_authenticate(user=user)
        detail_response = api_client.get(reverse("character-detail", args=[character.id]))
        assert detail_response.data["is_voted_by_me"] is True

    def test_vote_for_nonexistent_character_returns_404(self, auth_client):
        url = reverse("character-vote", args=[99999])
        response = auth_client.post(url)
        assert response.status_code == 404


class TestCharacterWriteEndpointsAreReadOnly:
    """Characters are populated exclusively via the SWAPI sync, never via direct API writes."""

    def test_create_not_allowed(self, auth_client):
        response = auth_client.post(reverse("character-list"), {"name": "Hand-crafted"})
        assert response.status_code == 405

    def test_update_not_allowed(self, auth_client, character):
        url = reverse("character-detail", args=[character.id])
        response = auth_client.patch(url, {"name": "Renamed"})
        assert response.status_code == 405

    def test_delete_not_allowed(self, auth_client, character):
        url = reverse("character-detail", args=[character.id])
        response = auth_client.delete(url)
        assert response.status_code == 405
