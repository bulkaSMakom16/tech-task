from django.db.models.deletion import ProtectedError
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from .models import Category, Location
from .permissions import CategoryPermission, LocationOwnerPermission
from .serializers import CategorySerializer, LocationSerializer


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
        locations = Location.objects.filter(deleted_at__isnull=True)
        return locations.order_by("-created_at", "-pk")

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def perform_destroy(self, location):
        location.soft_delete()
