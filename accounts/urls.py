from django.urls import path

from .views import LoginView, LogoutView, RegisterView, csrf_cookie


urlpatterns = [
    path("csrf/", csrf_cookie, name="csrf-cookie"),
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
]
