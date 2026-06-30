import pytest
import responses
from requests.exceptions import ConnectionError as RequestsConnectionError

from apps.common.exceptions import ExternalAPIError, ServiceUnavailableError
from apps.swapi_sync.services.client import SwapiClient


@pytest.fixture
def client():
    return SwapiClient(
        base_url="https://swapi.dev/api",
        timeout=1,
        max_retries=3,
        backoff_seconds=0,  # no real sleeping in tests
    )


class TestSwapiClientPagination:
    @responses.activate
    def test_iter_people_single_page(self, client):
        responses.add(
            responses.GET,
            "https://swapi.dev/api/people/",
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{"name": "Luke Skywalker", "url": "x"}],
            },
            status=200,
        )
        results = list(client.iter_people())
        assert len(results) == 1
        assert results[0]["name"] == "Luke Skywalker"

    @responses.activate
    def test_iter_films_follows_pagination(self, client):
        responses.add(
            responses.GET,
            "https://swapi.dev/api/films/",
            json={
                "count": 2,
                "next": "https://swapi.dev/api/films/?page=2",
                "previous": None,
                "results": [{"title": "A New Hope", "url": "f1"}],
            },
            status=200,
        )
        responses.add(
            responses.GET,
            "https://swapi.dev/api/films/?page=2",
            json={
                "count": 2,
                "next": None,
                "previous": "https://swapi.dev/api/films/",
                "results": [{"title": "Empire Strikes Back", "url": "f2"}],
            },
            status=200,
        )
        results = list(client.iter_films())
        assert [r["title"] for r in results] == ["A New Hope", "Empire Strikes Back"]

    @responses.activate
    def test_iter_starships_empty_results(self, client):
        responses.add(
            responses.GET,
            "https://swapi.dev/api/starships/",
            json={"count": 0, "next": None, "previous": None, "results": []},
            status=200,
        )
        assert list(client.iter_starships()) == []


class TestSwapiClientErrorHandling:
    @responses.activate
    def test_404_raises_external_api_error_without_retry(self, client):
        responses.add(responses.GET, "https://swapi.dev/api/people/", status=404)
        with pytest.raises(ExternalAPIError):
            list(client.iter_people())
        # 404 must not be retried — only one call should have been made.
        assert len(responses.calls) == 1

    @responses.activate
    def test_400_raises_external_api_error_without_retry(self, client):
        responses.add(
            responses.GET, "https://swapi.dev/api/people/", status=400, body="bad request"
        )
        with pytest.raises(ExternalAPIError):
            list(client.iter_people())
        assert len(responses.calls) == 1

    @responses.activate
    def test_500_is_retried_then_raises_service_unavailable(self, client):
        responses.add(responses.GET, "https://swapi.dev/api/people/", status=500)
        responses.add(responses.GET, "https://swapi.dev/api/people/", status=500)
        responses.add(responses.GET, "https://swapi.dev/api/people/", status=500)
        with pytest.raises(ServiceUnavailableError):
            list(client.iter_people())
        assert len(responses.calls) == 3  # exhausted all retries

    @responses.activate
    def test_500_then_200_succeeds_after_retry(self, client):
        responses.add(responses.GET, "https://swapi.dev/api/people/", status=500)
        responses.add(
            responses.GET,
            "https://swapi.dev/api/people/",
            json={
                "count": 1,
                "next": None,
                "previous": None,
                "results": [{"name": "Leia", "url": "x"}],
            },
            status=200,
        )
        results = list(client.iter_people())
        assert len(results) == 1
        assert len(responses.calls) == 2

    @responses.activate
    def test_connection_error_is_retried_then_raises_service_unavailable(self, client):
        responses.add(
            responses.GET,
            "https://swapi.dev/api/people/",
            body=RequestsConnectionError("connection refused"),
        )
        with pytest.raises(ServiceUnavailableError):
            list(client.iter_people())

    @responses.activate
    def test_non_json_response_raises_external_api_error(self, client):
        responses.add(
            responses.GET,
            "https://swapi.dev/api/people/",
            body="<html>not json</html>",
            status=200,
            content_type="text/html",
        )
        with pytest.raises(ExternalAPIError):
            list(client.iter_people())

    @responses.activate
    def test_get_resource_fetches_single_url(self, client):
        responses.add(
            responses.GET,
            "https://swapi.dev/api/planets/1/",
            json={"name": "Tatooine"},
            status=200,
        )
        data = client.get_resource("https://swapi.dev/api/planets/1/")
        assert data["name"] == "Tatooine"
