from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from locations.views import CategoryViewSet, LocationViewSet


router = DefaultRouter()
router.register("categories", CategoryViewSet)
router.register("locations", LocationViewSet)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/", include(router.urls)),
]
