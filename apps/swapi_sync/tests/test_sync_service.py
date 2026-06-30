import pytest
import responses

from apps.catalog.models import Character, Film, Starship
from apps.swapi_sync.services.client import SwapiClient
from apps.swapi_sync.services.sync import run_full_sync, sync_films

pytestmark = pytest.mark.django_db


def _mock_swapi(films=None, starships=None, people=None):
    """Register single-page mocked responses for all three SWAPI list endpoints."""
    responses.add(
        responses.GET,
        "https://swapi.dev/api/films/",
        json={"count": len(films or []), "next": None, "previous": None, "results": films or []},
        status=200,
    )
    responses.add(
        responses.GET,
        "https://swapi.dev/api/starships/",
        json={
            "count": len(starships or []),
            "next": None,
            "previous": None,
            "results": starships or [],
        },
        status=200,
    )
    responses.add(
        responses.GET,
        "https://swapi.dev/api/people/",
        json={"count": len(people or []), "next": None, "previous": None, "results": people or []},
        status=200,
    )


class TestRunFullSync:
    @responses.activate
    def test_creates_films_starships_characters(
        self, swapi_film_payload, swapi_starship_payload, swapi_people_payload
    ):
        _mock_swapi(
            films=[swapi_film_payload],
            starships=[swapi_starship_payload],
            people=[swapi_people_payload],
        )

        result = run_full_sync(client=SwapiClient())

        assert result.films_synced == 1
        assert result.starships_synced == 1
        assert result.characters_synced == 1
        assert result.errors == []
        assert Film.objects.count() == 1
        assert Starship.objects.count() == 1
        assert Character.objects.count() == 1

    @responses.activate
    def test_links_m2m_relationships_correctly(
        self, swapi_film_payload, swapi_starship_payload, swapi_people_payload
    ):
        _mock_swapi(
            films=[swapi_film_payload],
            starships=[swapi_starship_payload],
            people=[swapi_people_payload],
        )

        run_full_sync(client=SwapiClient())

        luke = Character.objects.get(name="Luke Skywalker")
        xwing = Starship.objects.get(name="X-wing")
        film = Film.objects.get(title="A New Hope")

        assert film in luke.films.all()
        assert xwing in luke.starships.all()
        assert film in xwing.films.all()

    @responses.activate
    def test_rerun_is_idempotent_no_duplicates(
        self, swapi_film_payload, swapi_starship_payload, swapi_people_payload
    ):
        _mock_swapi(
            films=[swapi_film_payload],
            starships=[swapi_starship_payload],
            people=[swapi_people_payload],
        )
        run_full_sync(client=SwapiClient())

        _mock_swapi(
            films=[swapi_film_payload],
            starships=[swapi_starship_payload],
            people=[swapi_people_payload],
        )
        result = run_full_sync(client=SwapiClient())

        assert Film.objects.count() == 1
        assert Starship.objects.count() == 1
        assert Character.objects.count() == 1
        assert result.films_synced == 1  # updated, not duplicated

    @responses.activate
    def test_rerun_updates_changed_fields(self, swapi_film_payload):
        _mock_swapi(films=[swapi_film_payload])
        run_full_sync(client=SwapiClient())

        updated_payload = dict(swapi_film_payload, title="A New Hope (Special Edition)")
        responses.reset()
        _mock_swapi(films=[updated_payload])
        run_full_sync(client=SwapiClient())

        assert Film.objects.count() == 1
        assert Film.objects.first().title == "A New Hope (Special Edition)"

    @responses.activate
    def test_partial_failure_does_not_abort_whole_sync(self, swapi_film_payload):
        bad_payload = {"title": "Broken Film"}  # missing required 'url' key
        responses.add(
            responses.GET,
            "https://swapi.dev/api/films/",
            json={
                "count": 2,
                "next": None,
                "previous": None,
                "results": [bad_payload, swapi_film_payload],
            },
            status=200,
        )

        from apps.swapi_sync.services.sync import SyncResult

        result = SyncResult()
        sync_films(SwapiClient(), result)

        assert result.films_synced == 1  # the good record still got through
        assert len(result.errors) == 1
        assert Film.objects.count() == 1


class TestDateAndIntParsing:
    @responses.activate
    def test_missing_release_date_handled_gracefully(self):
        payload = {
            "title": "Untitled",
            "episode_id": 99,
            "director": "",
            "producer": "",
            "release_date": None,
            "opening_crawl": "",
            "url": "https://swapi.dev/api/films/99/",
        }
        _mock_swapi(films=[payload])
        run_full_sync(client=SwapiClient())
        film = Film.objects.get(title="Untitled")
        assert film.release_date is None

    @responses.activate
    def test_non_numeric_height_mass_handled_gracefully(self, swapi_film_payload):
        person = {
            "name": "C-3PO",
            "height": "unknown",
            "mass": "unknown",
            "hair_color": "n/a",
            "skin_color": "gold",
            "eye_color": "yellow",
            "birth_year": "112BBY",
            "gender": "n/a",
            "films": [],
            "starships": [],
            "url": "https://swapi.dev/api/people/2/",
        }
        _mock_swapi(people=[person])
        run_full_sync(client=SwapiClient())
        droid = Character.objects.get(name="C-3PO")
        assert droid.height_cm is None
        assert droid.mass_kg is None
