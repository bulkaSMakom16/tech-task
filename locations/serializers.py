from rest_framework import serializers

from .models import Category, Location, Review, ReviewVote


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name")


class LocationSerializer(serializers.ModelSerializer):
    rating = serializers.FloatField(read_only=True, default=0)
    review_count = serializers.IntegerField(read_only=True, default=0)
    views_last_7_days = serializers.IntegerField(read_only=True, default=0)
    popularity = serializers.FloatField(read_only=True, default=0)

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
            "rating",
            "review_count",
            "views_last_7_days",
            "popularity",
        )
        read_only_fields = ("author", "created_at", "updated_at")

    def update(self, instance, validated_data):
        fields_to_save = ["updated_at"]
        for field, value in validated_data.items():
            setattr(instance, field, value)
            fields_to_save.append(field)

        instance.save(update_fields=fields_to_save)
        return instance


class ReviewSerializer(serializers.ModelSerializer):
    like_count = serializers.IntegerField(read_only=True, default=0)
    dislike_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Review
        fields = (
            "id",
            "location",
            "author",
            "rating",
            "comment",
            "like_count",
            "dislike_count",
        )
        read_only_fields = ("location", "author")


class ReviewVoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewVote
        fields = ("id", "value")
