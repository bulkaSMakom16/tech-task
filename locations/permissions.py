from rest_framework.permissions import SAFE_METHODS, BasePermission, IsAuthenticatedOrReadOnly


class CategoryPermission(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or request.user.is_staff


class LocationPermission(IsAuthenticatedOrReadOnly):
    def has_object_permission(self, request, view, location):
        if request.method in SAFE_METHODS or request.user.is_staff:
            return True

        return location.author_id == request.user.pk
