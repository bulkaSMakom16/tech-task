from django.db.models.deletion import ProtectedError
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.response import Response

from .models import Category, Location
from .permissions import IsCategoryAdminOrReadOnly, IsLocationOwnerOrAdminOrReadOnly
from .serializers import CategorySerializer, LocationSerializer


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.order_by("name")
    serializer_class = CategorySerializer
    permission_classes = [IsCategoryAdminOrReadOnly]

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "This category is assigned to a location."},
                status=status.HTTP_409_CONFLICT,
            )


class LocationViewSet(viewsets.ModelViewSet):
    queryset = Location.objects.filter(deleted_at__isnull=True).order_by("-created_at", "-pk")
    serializer_class = LocationSerializer
    permission_classes = [IsLocationOwnerOrAdminOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def perform_destroy(self, location):
        location.deleted_at = timezone.now()
        location.save(update_fields=["deleted_at", "updated_at"])
