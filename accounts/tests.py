from django.conf import settings
from rest_framework.test import APIClient, APITestCase


class SessionAuthenticationTests(APITestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)

    def csrf_headers(self):
        token = self.client.cookies[settings.CSRF_COOKIE_NAME].value
        return {"HTTP_X_CSRFTOKEN": token}

    def test_register_login_and_logout(self):
        response = self.client.get("/api/auth/csrf/")
        self.assertEqual(response.status_code, 200)

        credentials = {
            "username": "walker",
            "password": "Walk-by-the-river-27!",
        }
        response = self.client.post(
            "/api/auth/register/",
            {**credentials, "email": "walker@example.com"},
            format="json",
            **self.csrf_headers(),
        )
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("password", response.data)

        response = self.client.post(
            "/api/auth/login/",
            credentials,
            format="json",
            **self.csrf_headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.client.cookies[settings.SESSION_COOKIE_NAME].value)

        response = self.client.post("/api/auth/logout/", **self.csrf_headers())
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.post("/api/auth/logout/").status_code, 403)
