"""Sync service: translates SWAPI payloads into catalog model rows via idempotent upserts."""

import logging
from dataclasses import dataclass, field
from datetime import datetime

from django.db import transaction

from apps.catalog.models import Character, Film, Starship

from .client import SwapiClient

logger = logging.getLogger("apps.swapi_sync.sync")


@dataclass
class SyncResult:
    films_synced: int = 0
    starships_synced: int = 0
    characters_synced: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def total_synced(self) -> int:
        return self.films_synced + self.starships_synced + self.characters_synced

    def as_dict(self) -> dict:
        return {
            "films_synced": self.films_synced,
            "starships_synced": self.starships_synced,
            "characters_synced": self.characters_synced,
            "total_synced": self.total_synced,
            "errors": self.errors,
        }


def _parse_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_int(value: str | None):
    if not value:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _upsert_film(client: SwapiClient, data: dict) -> Film:
    film, _ = Film.objects.update_or_create(
        swapi_url=data["url"],
        defaults={
            "title": data.get("title", ""),
            "episode_id": data.get("episode_id") or 0,
            "director": data.get("director", ""),
            "producer": data.get("producer", ""),
            "release_date": _parse_date(data.get("release_date")),
            "opening_crawl": data.get("opening_crawl", ""),
        },
    )
    return film


def _upsert_starship(client: SwapiClient, data: dict) -> Starship:
    starship, _ = Starship.objects.update_or_create(
        swapi_url=data["url"],
        defaults={
            "name": data.get("name", ""),
            "model": data.get("model", ""),
            "starship_class": data.get("starship_class", ""),
            "manufacturer": data.get("manufacturer", ""),
            "cost_in_credits": data.get("cost_in_credits", ""),
            "length": data.get("length", ""),
            "crew": data.get("crew", ""),
            "passengers": data.get("passengers", ""),
            "hyperdrive_rating": data.get("hyperdrive_rating", ""),
        },
    )
    film_urls = data.get("films", [])
    if film_urls:
        films = Film.objects.filter(swapi_url__in=film_urls)
        starship.films.set(films)
    return starship


def _upsert_character(client: SwapiClient, data: dict) -> Character:
    character, _ = Character.objects.update_or_create(
        swapi_url=data["url"],
        defaults={
            "name": data.get("name", ""),
            "birth_year": data.get("birth_year", ""),
            "gender": data.get("gender", ""),
            "height_cm": _parse_int(data.get("height")),
            "mass_kg": _parse_int(data.get("mass")),
            "hair_color": data.get("hair_color", ""),
            "skin_color": data.get("skin_color", ""),
            "eye_color": data.get("eye_color", ""),
        },
    )
    film_urls = data.get("films", [])
    if film_urls:
        character.films.set(Film.objects.filter(swapi_url__in=film_urls))

    starship_urls = data.get("starships", [])
    if starship_urls:
        character.starships.set(Starship.objects.filter(swapi_url__in=starship_urls))

    return character


def sync_films(client: SwapiClient, result: SyncResult) -> None:
    for data in client.iter_films():
        try:
            with transaction.atomic():
                _upsert_film(client, data)
            result.films_synced += 1
        except (
            Exception
        ) as exc:  # noqa: BLE001 - intentionally broad: one bad record shouldn't abort the run
            logger.exception("Failed to sync film %s", data.get("url"))
            result.errors.append(f"film {data.get('url', '?')}: {exc}")


def sync_starships(client: SwapiClient, result: SyncResult) -> None:
    for data in client.iter_starships():
        try:
            with transaction.atomic():
                _upsert_starship(client, data)
            result.starships_synced += 1
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to sync starship %s", data.get("url"))
            result.errors.append(f"starship {data.get('url', '?')}: {exc}")


def sync_characters(client: SwapiClient, result: SyncResult) -> None:
    for data in client.iter_people():
        try:
            with transaction.atomic():
                _upsert_character(client, data)
            result.characters_synced += 1
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to sync character %s", data.get("url"))
            result.errors.append(f"character {data.get('url', '?')}: {exc}")


def run_full_sync(client: SwapiClient | None = None) -> SyncResult:
    """
    Sync the entire catalog from SWAPI: films, then starships, then
    characters (this order satisfies the M2M dependency chain). Returns a
    SyncResult summarising what happened, including any per-record errors
    that were swallowed so the rest of the sync could continue.
    """
    client = client or SwapiClient()
    result = SyncResult()

    logger.info("Starting full SWAPI sync")
    sync_films(client, result)
    sync_starships(client, result)
    sync_characters(client, result)
    logger.info("Finished full SWAPI sync: %s", result.as_dict())

    return result
