from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError
from rest_framework import serializers


User = get_user_model()


class RegistrationSerializer(serializers.ModelSerializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    class Meta:
        model = User
        fields = ("id", "username", "email", "password")

    def validate(self, attrs):
        user = User(username=attrs["username"], email=attrs["email"])
        try:
            password_validation.validate_password(attrs["password"], user)
        except ValidationError as error:
            raise serializers.ValidationError({"password": error.messages}) from error
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
