from datetime import timedelta

from django.core.cache import cache
from django.db import DatabaseError
from django.db.models import Avg, Count, F, OuterRef, Q, Subquery
from django.db.models.deletion import ProtectedError
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from .models import Category, Location, LocationVisit, Review, ReviewVote
from .permissions import CategoryPermission, LocationOwnerPermission
from .serializers import (
    CategorySerializer,
    LocationSerializer,
    ReviewSerializer,
    ReviewVoteSerializer,
)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.order_by("name")
    serializer_class = CategorySerializer
    permission_classes = [CategoryPermission]

    def destroy(self, request, *args, **kwargs):
        category = self.get_object()
        try:
            category.delete()
        except ProtectedError:
            return Response(
                {"detail": "This category is assigned to a location."},
                status=409,
            )

        return Response(status=204)


class LocationViewSet(viewsets.ModelViewSet):
    serializer_class = LocationSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, LocationOwnerPermission]

    def get_queryset(self):
        week_ago = timezone.now() - timedelta(days=7)
        visits = LocationVisit.objects.filter(location_id=OuterRef("pk"), created_at__gte=week_ago)
        visit_count = visits.values("location_id").annotate(total=Count("id")).values("total")

        locations = Location.objects.filter(deleted_at__isnull=True)
        locations = locations.annotate(
            rating=Avg("reviews__rating", default=0.0),
            review_count=Count("reviews"),
            views_last_7_days=Coalesce(Subquery(visit_count), 0),
        )
        locations = locations.annotate(
            popularity=F("rating") * 2 + F("review_count") + F("views_last_7_days"),
        )
        return locations.order_by("-created_at", "-pk")

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def perform_destroy(self, location):
        location.soft_delete()

    def retrieve(self, request, *args, **kwargs):
        location = self.get_object()
        if request.method == "GET" and self.record_visit(location):
            location = self.get_object()

        serializer = self.get_serializer(location)
        return Response(serializer.data)

    def record_visit(self, location):
        request = self.request
        if request.user.is_authenticated:
            visitor = f"user:{request.user.pk}"
        else:
            if request.session.session_key is None:
                request.session.create()
            visitor = f"guest:{request.session.session_key}"

        key = f"location-visit:{location.pk}:{visitor}"
        if not cache.add(key, True, timeout=3600):
            return False

        try:
            LocationVisit.objects.create(location=location)
        except DatabaseError:
            cache.delete(key)
            raise

        return True


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedOrReadOnly])
def location_reviews(request, location_id):
    location = get_object_or_404(Location, pk=location_id, deleted_at__isnull=True)

    if request.method == "GET":
        reviews = location.reviews.annotate(
            like_count=Count("votes", filter=Q(votes__value=ReviewVote.LIKE)),
            dislike_count=Count("votes", filter=Q(votes__value=ReviewVote.DISLIKE)),
        ).order_by("-pk")
        serializer = ReviewSerializer(reviews, many=True)
        return Response(serializer.data)

    serializer = ReviewSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    review, created = Review.objects.get_or_create(
        location=location,
        author=request.user,
        defaults=serializer.validated_data,
    )
    if not created:
        return Response({"detail": "You already reviewed this location."}, status=400)

    return Response(ReviewSerializer(review).data, status=201)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def vote_on_review(request, review_id):
    review = get_object_or_404(Review, pk=review_id, location__deleted_at__isnull=True)
    serializer = ReviewVoteSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    vote, created = ReviewVote.objects.get_or_create(
        review=review,
        user=request.user,
        defaults=serializer.validated_data,
    )
    if not created:
        return Response({"detail": "You already voted on this review."}, status=400)

    return Response(ReviewVoteSerializer(vote).data, status=201)
