from django.contrib import admin

from .models import Character, Film, Starship


@admin.register(Film)
class FilmAdmin(admin.ModelAdmin):
    list_display = ("title", "episode_id", "director", "release_date")
    search_fields = ("title", "director")
    ordering = ("episode_id",)


@admin.register(Starship)
class StarshipAdmin(admin.ModelAdmin):
    list_display = ("name", "model", "manufacturer", "starship_class")
    search_fields = ("name", "model", "manufacturer")
    filter_horizontal = ("films",)


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ("name", "birth_year", "gender")
    search_fields = ("name",)
    filter_horizontal = ("films", "starships")
