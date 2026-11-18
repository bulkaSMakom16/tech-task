from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase

from locations.models import Category


class SessionAuthenticationTests(APITestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.credentials = {
            "username": "walker",
            "password": "Walk-by-the-river-27!",
        }

    def csrf_headers(self):
        return {"HTTP_X_CSRFTOKEN": self.client.cookies[settings.CSRF_COOKIE_NAME].value}

    def test_register_login_and_logout(self):
        response = self.client.get("/api/auth/csrf/")
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            "/api/auth/register/",
            {**self.credentials, "email": "walker@example.com"},
            format="json",
            **self.csrf_headers(),
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertNotIn("password", response.data)
        user = get_user_model().objects.get(username="walker")
        self.assertTrue(user.check_password(self.credentials["password"]))

        response = self.client.post(
            "/api/auth/login/", self.credentials, format="json", **self.csrf_headers()
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["id"], user.pk)
        self.assertTrue(self.client.cookies[settings.SESSION_COOKIE_NAME].value)

        category = Category.objects.create(name="Parks")
        response = self.client.post(
            "/api/locations/",
            {
                "name": "City park",
                "description": "A park by the river.",
                "category": category.pk,
                "address": "Riverside Street 1",
                "latitude": "48.464717",
                "longitude": "35.046183",
            },
            format="json",
            **self.csrf_headers(),
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["author"], user.pk)

        response = self.client.post("/api/auth/logout/", **self.csrf_headers())
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.post("/api/auth/logout/").status_code, 403)

    def test_login_requires_csrf_for_guest(self):
        get_user_model().objects.create_user(**self.credentials)
        response = self.client.post("/api/auth/login/", self.credentials, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(settings.SESSION_COOKIE_NAME, self.client.cookies)

    def test_registration_requires_csrf_for_guest(self):
        response = self.client.post(
            "/api/auth/register/",
            {**self.credentials, "email": "walker@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(get_user_model().objects.filter(username="walker").exists())
