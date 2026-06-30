import pytest
from django.urls import reverse

from apps.catalog.models import Starship

pytestmark = pytest.mark.django_db


class TestStarshipListEndpoint:
    def test_list_returns_starships(self, api_client, starship):
        response = api_client.get(reverse("starship-list"))
        assert response.status_code == 200
        assert response.data["results"][0]["name"] == "X-wing"

    def test_search_by_manufacturer(self, api_client, starship, db):
        Starship.objects.create(
            swapi_url="https://swapi.dev/api/starships/9/",
            name="Death Star",
            manufacturer="Imperial Department of Military Research",
        )
        response = api_client.get(reverse("starship-list"), {"search": "Incom"})
        names = [r["name"] for r in response.data["results"]]
        assert names == ["X-wing"]


class TestStarshipDetailEndpoint:
    def test_retrieve_includes_film_titles(self, api_client, starship, film):
        url = reverse("starship-detail", args=[starship.id])
        response = api_client.get(url)
        assert response.status_code == 200
        assert response.data["films"] == ["A New Hope"]
        assert response.data["hyperdrive_rating"] == "1.0"


class TestStarshipVoteEndpoint:
    def test_vote_and_unvote_round_trip(self, auth_client, starship):
        url = reverse("starship-vote", args=[starship.id])
        first = auth_client.post(url)
        second = auth_client.post(url)
        assert first.data["voted"] is True
        assert second.data["voted"] is False
        assert second.data["item"]["vote_count"] == 0
