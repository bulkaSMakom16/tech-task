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
            "id",
            "name",
            "description",
            "category",
            "address",
            "latitude",
            "longitude",
            "author",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("author", "created_at", "updated_at")

    def update(self, instance, validated_data):
        fields_to_save = ["updated_at"]
        for field, value in validated_data.items():
            setattr(instance, field, value)
            fields_to_save.append(field)

        # Saving only these fields preserves a simultaneous soft delete.
        instance.save(update_fields=fields_to_save)
        return instance
