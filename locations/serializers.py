from rest_framework import serializers

from .models import Category, Location


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name")


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = (
            "id", "name", "description", "category", "address", "latitude", "longitude",
            "author", "created_at", "updated_at",
        )
        read_only_fields = ("author", "created_at", "updated_at")

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        # Preserve a soft deletion recorded after the instance was loaded.
        instance.save(update_fields=[*validated_data, "updated_at"])
        return instance
