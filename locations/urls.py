from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, LocationViewSet


router = DefaultRouter()
router.register("categories", CategoryViewSet)
router.register("locations", LocationViewSet)

urlpatterns = router.urls
