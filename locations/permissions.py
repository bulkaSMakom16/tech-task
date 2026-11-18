from rest_framework.permissions import SAFE_METHODS, BasePermission


class CategoryPermission(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or request.user.is_staff


class LocationPermission(BasePermission):
    def has_object_permission(self, request, view, location):
        return (
            request.method in SAFE_METHODS
            or request.user.is_staff
            or location.author_id == request.user.pk
        )
