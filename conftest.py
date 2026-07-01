"""Shared pytest fixtures — available to all tests without explicit import."""

import pytest
from rest_framework.test import APIClient

from apps.catalog.models import Character, Film, Starship


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(
        username="testuser", email="testuser@example.com", password="StrongPass123!"
    )


@pytest.fixture
def other_user(django_user_model):
    return django_user_model.objects.create_user(
        username="otheruser", email="otheruser@example.com", password="StrongPass123!"
    )


@pytest.fixture
def admin_user(django_user_model):
    return django_user_model.objects.create_superuser(
        username="admin", email="admin@example.com", password="StrongPass123!"
    )


@pytest.fixture
def auth_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def admin_client_jwt(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def film(db):
    return Film.objects.create(
        swapi_url="https://swapi.dev/api/films/1/",
        title="A New Hope",
        episode_id=4,
        director="George Lucas",
        producer="Gary Kurtz",
        release_date="1977-05-25",
        opening_crawl="It is a period of civil war...",
    )


@pytest.fixture
def starship(db, film):
    ship = Starship.objects.create(
        swapi_url="https://swapi.dev/api/starships/12/",
        name="X-wing",
        model="T-65 X-wing",
        manufacturer="Incom Corporation",
        starship_class="Starfighter",
        cost_in_credits="149999",
        length="12.5",
        crew="1",
        passengers="0",
        hyperdrive_rating="1.0",
    )
    ship.films.add(film)
    return ship


@pytest.fixture
def character(db, film, starship):
    person = Character.objects.create(
        swapi_url="https://swapi.dev/api/people/1/",
        name="Luke Skywalker",
        birth_year="19BBY",
        gender="male",
        height_cm=172,
        mass_kg=77,
        hair_color="blond",
        skin_color="fair",
        eye_color="blue",
    )
    person.films.add(film)
    person.starships.add(starship)
    return person


@pytest.fixture
def swapi_film_payload():
    return {
        "title": "A New Hope",
        "episode_id": 4,
        "director": "George Lucas",
        "producer": "Gary Kurtz",
        "release_date": "1977-05-25",
        "opening_crawl": "It is a period of civil war...",
        "url": "https://swapi.dev/api/films/1/",
    }


@pytest.fixture
def swapi_starship_payload():
    return {
        "name": "X-wing",
        "model": "T-65 X-wing",
        "manufacturer": "Incom Corporation",
        "cost_in_credits": "149999",
        "length": "12.5",
        "crew": "1",
        "passengers": "0",
        "hyperdrive_rating": "1.0",
        "starship_class": "Starfighter",
        "films": ["https://swapi.dev/api/films/1/"],
        "url": "https://swapi.dev/api/starships/12/",
    }


@pytest.fixture
def swapi_people_payload():
    return {
        "name": "Luke Skywalker",
        "height": "172",
        "mass": "77",
        "hair_color": "blond",
        "skin_color": "fair",
        "eye_color": "blue",
        "birth_year": "19BBY",
        "gender": "male",
        "films": ["https://swapi.dev/api/films/1/"],
        "starships": ["https://swapi.dev/api/starships/12/"],
        "url": "https://swapi.dev/api/people/1/",
    }
