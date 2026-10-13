from rest_framework.routers import DefaultRouter

from .views import FitnessClassViewSet, StudioViewSet

router = DefaultRouter()
router.register("studios", StudioViewSet, basename="studio")
router.register("classes", FitnessClassViewSet, basename="fitness-class")

urlpatterns = router.urls