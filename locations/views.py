from csv import QUOTE_ALL
from datetime import timedelta
from hashlib import sha256
from uuid import uuid4

import pandas as pd
from django.core.cache import cache
from django.db import DatabaseError, transaction
from django.db.models import Avg, Count, F, OuterRef, Q, Subquery
from django.db.models.deletion import ProtectedError
from django.db.models.functions import Coalesce
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.filters import SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from .filters import LocationFilter, LocationOrderingFilter
from .models import Category, Location, LocationVisit, Review, ReviewVote
from .permissions import CategoryPermission, LocationOwnerPermission
from .serializers import (
    CategorySerializer,
    LocationSerializer,
    ReviewSerializer,
    ReviewVoteSerializer,
)


LIST_VERSION_KEY = "locations:list:version"


def location_list_cache_key(request):
    new_version = str(uuid4())
    version = cache.get_or_set(LIST_VERSION_KEY, new_version, timeout=None)

    url = request.build_absolute_uri()
    url_bytes = url.encode("utf-8")
    url_hash = sha256(url_bytes).hexdigest()

    return f"locations:list:{version}:{url_hash}"


def clear_location_list_cache():
    cache.delete(LIST_VERSION_KEY)


def csv_text(value):
    formula_prefixes = ("=", "+", "-", "@", "＝", "＋", "－", "＠")
    if value.startswith(("\t", "\r", "\n")) or value.lstrip().startswith(formula_prefixes):
        return "'" + value

    return value


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

        transaction.on_commit(clear_location_list_cache, robust=True)
        return Response(status=204)


class LocationViewSet(viewsets.ModelViewSet):
    serializer_class = LocationSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, LocationOwnerPermission]
    filter_backends = [DjangoFilterBackend, SearchFilter, LocationOrderingFilter]
    filterset_class = LocationFilter
    search_fields = ["name", "description"]
    ordering_fields = ["created_at", "rating", "popularity"]

    def get_queryset(self):
        week_ago = timezone.now() - timedelta(days=7)
        visits = LocationVisit.objects.filter(
            location_id=OuterRef("pk"),
            created_at__gte=week_ago,
        )
        visits = visits.values("location_id")
        visits = visits.annotate(total=Count("id"))
        visit_count = Subquery(visits.values("total"))

        locations = Location.objects.filter(deleted_at__isnull=True)
        locations = locations.annotate(
            rating=Avg("reviews__rating", default=0.0),
            review_count=Count("reviews"),
            views_last_7_days=Coalesce(visit_count, 0),
        )

        rating_points = F("rating") * 2
        popularity = rating_points + F("review_count") + F("views_last_7_days")
        locations = locations.annotate(popularity=popularity)
        return locations

    def filter_queryset(self, queryset):
        if self.action in ("list", "export"):
            return super().filter_queryset(queryset)

        return queryset

    def list(self, request, *args, **kwargs):
        if request.accepted_renderer.format != "json":
            return super().list(request, *args, **kwargs)

        cache_key = location_list_cache_key(request)
        data = cache.get(cache_key)
        if data is not None:
            return Response(data)

        response = super().list(request, *args, **kwargs)
        cache.set(cache_key, response.data, timeout=60)
        return response

    @action(detail=False, methods=["get"])
    def export(self, request, *args, **kwargs):
        file_type = request.query_params.get("file_type", "json")
        if file_type not in ("json", "csv"):
            return Response({"detail": "Choose json or csv."}, status=400)

        locations = self.get_queryset()
        locations = self.filter_queryset(locations)
        serializer = self.get_serializer(locations, many=True)
        data = serializer.data

        if file_type == "csv":
            table = pd.DataFrame(data, columns=LocationSerializer.Meta.fields)
            for column in ("name", "description", "address"):
                table[column] = table[column].map(csv_text)

            csv_data = table.to_csv(index=False, quoting=QUOTE_ALL, lineterminator="\r\n")
            response = HttpResponse(csv_data, content_type="text/csv; charset=utf-8")
        else:
            response = JsonResponse(data, safe=False, json_dumps_params={"ensure_ascii": False})

        response["Content-Disposition"] = f'attachment; filename="locations.{file_type}"'
        return response

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)
        transaction.on_commit(clear_location_list_cache, robust=True)

    def perform_update(self, serializer):
        serializer.save()
        transaction.on_commit(clear_location_list_cache, robust=True)

    def perform_destroy(self, location):
        location.soft_delete()
        transaction.on_commit(clear_location_list_cache, robust=True)

    def retrieve(self, request, *args, **kwargs):
        location = self.get_object()

        visit_added = False
        if request.method == "GET":
            visit_added = self.record_visit(location)

        if visit_added:
            location = self.get_object()

        serializer = self.get_serializer(location)
        return Response(serializer.data)

    def record_visit(self, location):
        request = self.request
        if request.user.is_authenticated:
            visitor = f"user:{request.user.pk}"
        else:
            session = request.session
            if session.session_key is None:
                session.create()
            visitor = f"guest:{session.session_key}"

        cache_key = f"location-visit:{location.pk}:{visitor}"
        first_visit_this_hour = cache.add(cache_key, True, timeout=3600)
        if not first_visit_this_hour:
            return False

        try:
            LocationVisit.objects.create(location=location)
        except DatabaseError:
            cache.delete(cache_key)
            raise

        transaction.on_commit(clear_location_list_cache, robust=True)
        return True


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedOrReadOnly])
def location_reviews(request, location_id):
    location = get_object_or_404(Location, pk=location_id, deleted_at__isnull=True)

    if request.method == "GET":
        likes = Q(votes__value=ReviewVote.LIKE)
        dislikes = Q(votes__value=ReviewVote.DISLIKE)
        reviews = location.reviews.annotate(
            like_count=Count("votes", filter=likes),
            dislike_count=Count("votes", filter=dislikes),
        )
        reviews = reviews.order_by("-pk")
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(reviews, request)
        serializer = ReviewSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    serializer = ReviewSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    review, review_created = Review.objects.get_or_create(
        location=location,
        author=request.user,
        defaults=serializer.validated_data,
    )
    if not review_created:
        return Response(
            {"detail": "You already reviewed this location."},
            status=400,
        )

    transaction.on_commit(clear_location_list_cache, robust=True)
    serializer = ReviewSerializer(review)
    return Response(serializer.data, status=201)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def vote_on_review(request, review_id):
    review = get_object_or_404(
        Review,
        pk=review_id,
        location__deleted_at__isnull=True,
    )

    serializer = ReviewVoteSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    vote, vote_created = ReviewVote.objects.get_or_create(
        review=review,
        user=request.user,
        defaults=serializer.validated_data,
    )
    if not vote_created:
        return Response(
            {"detail": "You already voted on this review."},
            status=400,
        )

    serializer = ReviewVoteSerializer(vote)
    return Response(serializer.data, status=201)
