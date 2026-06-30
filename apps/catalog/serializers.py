from rest_framework import serializers

from apps.voting.services import has_user_voted

from .models import Character, Film, Starship


class _VoteAwareSerializer(serializers.ModelSerializer):
    """
    Mixin adding `vote_count` and `is_voted_by_me` to any catalog
    serializer. `vote_count` is expected to be annotated onto the queryset
    by the view (see catalog/views.py) for efficiency — falling back to a
    per-instance count() only if it wasn't, so the serializer still works
    correctly (just less efficiently) if used standalone.
    """

    vote_count = serializers.SerializerMethodField()
    is_voted_by_me = serializers.SerializerMethodField()

    def get_vote_count(self, obj) -> int:
        annotated = getattr(obj, "annotated_vote_count", None)
        if annotated is not None:
            return annotated
        from apps.voting.services import vote_count_for

        return vote_count_for(obj)

    def get_is_voted_by_me(self, obj) -> bool:
        annotated = getattr(obj, "annotated_is_voted", None)
        if annotated is not None:
            return bool(annotated)

        request = self.context.get("request")
        if request is None:
            return False
        return has_user_voted(request.user, obj)


class FilmListSerializer(_VoteAwareSerializer):
    class Meta:
        model = Film
        fields = (
            "id",
            "title",
            "episode_id",
            "director",
            "release_date",
            "vote_count",
            "is_voted_by_me",
        )


class FilmDetailSerializer(_VoteAwareSerializer):
    characters = serializers.SerializerMethodField()
    starships = serializers.SerializerMethodField()

    class Meta:
        model = Film
        fields = (
            "id",
            "title",
            "episode_id",
            "director",
            "producer",
            "release_date",
            "opening_crawl",
            "characters",
            "starships",
            "vote_count",
            "is_voted_by_me",
            "created_at",
            "updated_at",
        )

    def get_characters(self, obj) -> list:
        return list(obj.characters.values_list("id", "name"))

    def get_starships(self, obj) -> list:
        return list(obj.starships.values_list("id", "name"))


class StarshipListSerializer(_VoteAwareSerializer):
    class Meta:
        model = Starship
        fields = (
            "id",
            "name",
            "model",
            "manufacturer",
            "starship_class",
            "vote_count",
            "is_voted_by_me",
        )


class StarshipDetailSerializer(_VoteAwareSerializer):
    films = serializers.SlugRelatedField(many=True, read_only=True, slug_field="title")

    class Meta:
        model = Starship
        fields = (
            "id",
            "name",
            "model",
            "manufacturer",
            "starship_class",
            "cost_in_credits",
            "length",
            "crew",
            "passengers",
            "hyperdrive_rating",
            "films",
            "vote_count",
            "is_voted_by_me",
            "created_at",
            "updated_at",
        )


class CharacterListSerializer(_VoteAwareSerializer):
    class Meta:
        model = Character
        fields = (
            "id",
            "name",
            "birth_year",
            "gender",
            "vote_count",
            "is_voted_by_me",
        )


class CharacterDetailSerializer(_VoteAwareSerializer):
    films = serializers.SlugRelatedField(many=True, read_only=True, slug_field="title")
    starships = serializers.SlugRelatedField(many=True, read_only=True, slug_field="name")

    class Meta:
        model = Character
        fields = (
            "id",
            "name",
            "birth_year",
            "gender",
            "height_cm",
            "mass_kg",
            "hair_color",
            "skin_color",
            "eye_color",
            "films",
            "starships",
            "vote_count",
            "is_voted_by_me",
            "created_at",
            "updated_at",
        )
