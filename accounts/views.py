from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .serializers import LoginSerializer, RegistrationSerializer


@require_GET
def csrf_cookie(request):
    get_token(request)
    return JsonResponse({"detail": "CSRF cookie set."})


@api_view(["POST"])
@csrf_protect
def register_user(request):
    serializer = RegistrationSerializer(data=request.data)
    serializer.is_valid()
    serializer.save()
    return Response(serializer.data, status=201)


@api_view(["POST"])
@csrf_protect
def login_user(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid()
    username = serializer.validated_data["username"]
    password = serializer.validated_data["password"]
    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response(
            {"detail": "Invalid username or password."},
            status=400,
        )

    login(request, user)
    return Response({"id": user.pk, "username": user.username})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_user(request):
    logout(request)
    return Response(status=204)
