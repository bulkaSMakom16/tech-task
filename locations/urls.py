from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CategoryViewSet,
    LocationViewSet,
    location_reviews,
    location_subscription,
    vote_on_review,
)


router = DefaultRouter()
router.register("categories", CategoryViewSet)
router.register("locations", LocationViewSet, basename="location")

urlpatterns = [
    path("locations/<int:location_id>/reviews/", location_reviews, name="location-reviews"),
    path(
        "locations/<int:location_id>/subscription/",
        location_subscription,
        name="location-subscription",
    ),
    path("reviews/<int:review_id>/votes/", vote_on_review, name="review-votes"),
] + router.urls
