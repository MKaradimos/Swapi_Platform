from django.db import models

from apps.common.models import TimeStampedModel


class Film(TimeStampedModel):
    """A single Star Wars film, sourced from SWAPI's /films/ endpoint."""

    swapi_url = models.URLField(
        unique=True,
        db_index=True,
        help_text="Canonical SWAPI resource URL; used as the natural key for upserts.",
    )
    title = models.CharField(max_length=255, db_index=True)
    episode_id = models.PositiveSmallIntegerField()
    director = models.CharField(max_length=255, blank=True)
    producer = models.CharField(max_length=255, blank=True)
    release_date = models.DateField(null=True, blank=True)
    opening_crawl = models.TextField(blank=True)

    class Meta:
        ordering = ["episode_id"]

    def __str__(self):
        return f"Episode {self.episode_id}: {self.title}"


class Starship(TimeStampedModel):
    """A single starship, sourced from SWAPI's /starships/ endpoint."""

    swapi_url = models.URLField(unique=True, db_index=True)
    name = models.CharField(max_length=255, db_index=True)
    model = models.CharField(max_length=255, blank=True)
    starship_class = models.CharField(max_length=255, blank=True)
    manufacturer = models.CharField(max_length=255, blank=True)
    cost_in_credits = models.CharField(
        max_length=64,
        blank=True,
        help_text="Stored as text: SWAPI returns 'unknown' for some values.",
    )
    length = models.CharField(max_length=64, blank=True)
    crew = models.CharField(max_length=64, blank=True)
    passengers = models.CharField(max_length=64, blank=True)
    hyperdrive_rating = models.CharField(max_length=64, blank=True)

    films = models.ManyToManyField(Film, related_name="starships", blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Character(TimeStampedModel):
    """A single character/person, sourced from SWAPI's /people/ endpoint."""

    swapi_url = models.URLField(unique=True, db_index=True)
    name = models.CharField(max_length=255, db_index=True)
    birth_year = models.CharField(max_length=32, blank=True)
    gender = models.CharField(max_length=32, blank=True)
    height_cm = models.PositiveIntegerField(null=True, blank=True)
    mass_kg = models.PositiveIntegerField(null=True, blank=True)
    hair_color = models.CharField(max_length=64, blank=True)
    skin_color = models.CharField(max_length=64, blank=True)
    eye_color = models.CharField(max_length=64, blank=True)

    films = models.ManyToManyField(Film, related_name="characters", blank=True)
    starships = models.ManyToManyField(Starship, related_name="pilots", blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Character"
        verbose_name_plural = "Characters"

    def __str__(self):
        return self.name
