from django_filters import rest_framework as filters
from rest_framework.filters import OrderingFilter

from .models import Location


class LocationFilter(filters.FilterSet):
    rating = filters.NumberFilter(field_name="rating")

    class Meta:
        model = Location
        fields = ("category", "author", "rating")


class LocationOrderingFilter(OrderingFilter):
    def get_ordering(self, request, queryset, view):
        ordering = super().get_ordering(request, queryset, view)
        if not ordering:
            return ["-created_at", "-pk"]

        return list(ordering) + ["-pk"]
