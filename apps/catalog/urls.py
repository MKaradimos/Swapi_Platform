from rest_framework.routers import DefaultRouter

from .views import CharacterViewSet, FilmViewSet, StarshipViewSet

router = DefaultRouter()
router.register("characters", CharacterViewSet, basename="character")
router.register("films", FilmViewSet, basename="film")
router.register("starships", StarshipViewSet, basename="starship")

urlpatterns = router.urls
