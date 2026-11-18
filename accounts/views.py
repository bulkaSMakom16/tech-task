from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import PasswordResetForm
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_safe
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .serializers import LoginSerializer, RegistrationSerializer


@require_GET
def csrf_cookie(request):
    get_token(request)
    return JsonResponse({"detail": "csrf set."})


@api_view(["POST"])
@csrf_protect
def register_user(request):
    serializer = RegistrationSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    serializer.save()
    return Response(serializer.data, status=201)


@api_view(["POST"])
@csrf_protect
def login_user(request):
    serializer = LoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    username = serializer.validated_data["username"]
    password = serializer.validated_data["password"]
    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response(
            {"detail": "invalid user or pass."},
            status=400,
        )

    login(request, user)
    return Response({"id": user.pk, "username": user.username})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_user(request):
    logout(request)
    return Response(status=204)


@api_view(["POST"])
@csrf_protect
def password_reset(request):
    form = PasswordResetForm(request.data)
    if not form.is_valid():
        return Response(form.errors, status=400)

    form.save(request=request, use_https=request.is_secure())
    return Response({"detail": "if the email is registered, youll receive a reset link"})


@require_safe
def password_reset_done(request):
    return render(request, "accounts/password_reset_complete.html")
