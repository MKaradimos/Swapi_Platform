import pytest
from django.db import IntegrityError

from apps.catalog.models import Character, Film

pytestmark = pytest.mark.django_db


class TestFilmModel:
    def test_str_representation(self, film):
        assert str(film) == "Episode 4: A New Hope"

    def test_swapi_url_must_be_unique(self, film):
        with pytest.raises(IntegrityError):
            Film.objects.create(
                swapi_url=film.swapi_url,  # duplicate
                title="Duplicate",
                episode_id=99,
            )

    def test_ordering_by_episode_id(self, db):
        Film.objects.create(
            swapi_url="https://swapi.dev/api/films/5/", title="Episode V", episode_id=5
        )
        Film.objects.create(
            swapi_url="https://swapi.dev/api/films/2/", title="Episode II", episode_id=2
        )
        Film.objects.create(
            swapi_url="https://swapi.dev/api/films/4/", title="Episode IV", episode_id=4
        )
        episode_ids = list(Film.objects.values_list("episode_id", flat=True))
        assert episode_ids == sorted(episode_ids)


class TestStarshipModel:
    def test_str_representation(self, starship):
        assert str(starship) == "X-wing"

    def test_film_relationship(self, starship, film):
        assert film in starship.films.all()
        assert starship in film.starships.all()


class TestCharacterModel:
    def test_str_representation(self, character):
        assert str(character) == "Luke Skywalker"

    def test_film_and_starship_relationships(self, character, film, starship):
        assert film in character.films.all()
        assert starship in character.starships.all()
        assert character in starship.pilots.all()

    def test_optional_numeric_fields_can_be_null(self, db):
        droid = Character.objects.create(
            swapi_url="https://swapi.dev/api/people/2/",
            name="C-3PO",
            height_cm=None,
            mass_kg=None,
        )
        assert droid.height_cm is None
        assert droid.mass_kg is None
