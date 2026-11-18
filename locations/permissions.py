from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsCategoryAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or request.user.is_staff


class IsLocationOwnerOrAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or request.user.is_authenticated

    def has_object_permission(self, request, view, location):
        return (
            request.method in SAFE_METHODS
            or request.user.is_staff
            or location.author_id == request.user.pk
        )
