import pytest
from django.urls import reverse

from apps.catalog.models import Film

pytestmark = pytest.mark.django_db


class TestFilmListEndpoint:
    def test_list_returns_films(self, api_client, film):
        response = api_client.get(reverse("film-list"))
        assert response.status_code == 200
        assert response.data["results"][0]["title"] == "A New Hope"

    def test_filter_by_episode_id(self, api_client, film, db):
        Film.objects.create(
            swapi_url="https://swapi.dev/api/films/5/",
            title="The Empire Strikes Back",
            episode_id=5,
        )
        response = api_client.get(reverse("film-list"), {"episode_id": 4})
        titles = [r["title"] for r in response.data["results"]]
        assert titles == ["A New Hope"]

    def test_default_ordering_by_episode_id(self, api_client, db):
        Film.objects.create(
            swapi_url="https://swapi.dev/api/films/6/", title="Episode VI", episode_id=6
        )
        Film.objects.create(
            swapi_url="https://swapi.dev/api/films/1/", title="Episode I", episode_id=1
        )
        response = api_client.get(reverse("film-list"))
        episode_ids = [r["episode_id"] for r in response.data["results"]]
        assert episode_ids == sorted(episode_ids)


class TestFilmDetailEndpoint:
    def test_retrieve_includes_characters_and_starships(
        self, api_client, film, character, starship
    ):
        url = reverse("film-detail", args=[film.id])
        response = api_client.get(url)
        assert response.status_code == 200
        assert [c[1] for c in response.data["characters"]] == ["Luke Skywalker"]
        assert [s[1] for s in response.data["starships"]] == ["X-wing"]
        assert "opening_crawl" in response.data


class TestFilmVoteEndpoint:
    def test_vote_on_film(self, auth_client, film):
        url = reverse("film-vote", args=[film.id])
        response = auth_client.post(url)
        assert response.status_code == 201
        assert response.data["item"]["vote_count"] == 1
