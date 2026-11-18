from django.urls import path

from .views import csrf_cookie, login_user, logout_user, register_user


urlpatterns = [
    path("csrf/", csrf_cookie, name="csrf-cookie"),
    path("register/", register_user, name="register"),
    path("login/", login_user, name="login"),
    path("logout/", logout_user, name="logout"),
]
