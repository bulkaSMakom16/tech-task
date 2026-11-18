from django.contrib.auth.views import PasswordResetConfirmView
from django.urls import path

from .views import (
    csrf_cookie,
    login_user,
    logout_user,
    password_reset,
    password_reset_done,
    register_user,
)


urlpatterns = [
    path("csrf/", csrf_cookie, name="csrf-cookie"),
    path("register/", register_user, name="register"),
    path("login/", login_user, name="login"),
    path("logout/", logout_user, name="logout"),
    path("password-reset/", password_reset, name="password_reset"),
    path("password-reset/done/", password_reset_done, name="password_reset_complete"),
    path(
        "password-reset/<uidb64>/<token>/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
]
