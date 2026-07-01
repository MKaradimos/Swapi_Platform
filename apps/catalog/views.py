from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Exists, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.voting.models import Vote
from apps.voting.services import cast_vote

from .models import Character, Film, Starship
from .serializers import (
    CharacterDetailSerializer,
    CharacterListSerializer,
    FilmDetailSerializer,
    FilmListSerializer,
    StarshipDetailSerializer,
    StarshipListSerializer,
)


def _with_vote_annotations(queryset, model, user):
    """Annotate queryset with vote_count and is_voted via correlated subqueries (avoids N+1)."""
    content_type = ContentType.objects.get_for_model(model)

    vote_counts = (
        Vote.objects.filter(content_type=content_type, object_id=OuterRef("pk"))
        .values("object_id")
        .annotate(count=Count("id"))
        .values("count")
    )
    # Coalesce to 0: subquery returns NULL for items with zero votes.
    queryset = queryset.annotate(annotated_vote_count=Coalesce(Subquery(vote_counts), Value(0)))

    if user is not None and user.is_authenticated:
        is_voted = Vote.objects.filter(
            content_type=content_type, object_id=OuterRef("pk"), user=user
        )
        queryset = queryset.annotate(annotated_is_voted=Exists(is_voted))
    else:
        queryset = queryset.annotate(annotated_is_voted=Value(False))

    return queryset


class _VotableViewSetMixin:
    """Shared `vote` action for any catalog viewset (toggle vote/un-vote)."""

    @action(
        detail=True,
        methods=["post"],
        url_path="vote",
        throttle_classes=[ScopedRateThrottle],
    )
    def vote(self, request, pk=None):
        instance = self.get_object()
        _vote, created = cast_vote(request.user, instance)

            # Re-fetch to get updated vote count after mutation.
        instance = self.get_queryset().get(pk=instance.pk)
        serializer = self.get_serializer(instance)
        return Response(
            {"voted": created, "item": serializer.data},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    vote.throttle_scope = "vote"


class FilmViewSet(_VotableViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    Read-only catalog of films, plus a `/vote/` action.

    Films are populated exclusively via the SWAPI sync process (see
    apps.swapi_sync) rather than direct create/update/delete through this
    API.
    """

    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filterset_fields = ["episode_id"]
    search_fields = ["title", "director", "producer"]
    ordering_fields = ["title", "episode_id", "release_date"]
    ordering = ["episode_id"]

    def get_queryset(self):
        return _with_vote_annotations(Film.objects.all(), Film, self.request.user)

    def get_serializer_class(self):
        return FilmDetailSerializer if self.action == "retrieve" else FilmListSerializer


class StarshipViewSet(_VotableViewSetMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filterset_fields = ["starship_class", "manufacturer"]
    search_fields = ["name", "model", "manufacturer"]
    ordering_fields = ["name"]
    ordering = ["name"]

    def get_queryset(self):
        return _with_vote_annotations(
            Starship.objects.prefetch_related("films"), Starship, self.request.user
        )

    def get_serializer_class(self):
        return StarshipDetailSerializer if self.action == "retrieve" else StarshipListSerializer


class CharacterViewSet(_VotableViewSetMixin, viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filterset_fields = ["gender"]
    search_fields = ["name", "birth_year"]
    ordering_fields = ["name", "birth_year"]
    ordering = ["name"]

    def get_queryset(self):
        qs = Character.objects.prefetch_related("films", "starships")
        return _with_vote_annotations(qs, Character, self.request.user)

    def get_serializer_class(self):
        return CharacterDetailSerializer if self.action == "retrieve" else CharacterListSerializer
