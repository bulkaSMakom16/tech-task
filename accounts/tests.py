from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
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

    def test_missing_password_returns_400(self):
        self.client.get("/api/auth/csrf/")
        for path in ("/api/auth/register/", "/api/auth/login/"):
            response = self.client.post(
                path,
                {"username": "walker", "email": "walker@example.com"},
                format="json",
                **self.csrf_headers(),
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn("password", response.data)


class PasswordResetTests(APITestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.user = get_user_model().objects.create_user(
            username="walker",
            email="walker@example.com",
            password="Walk-by-the-river-27!",
        )
        self.url = "/api/auth/password-reset/"

    def csrf_headers(self):
        return {"HTTP_X_CSRFTOKEN": self.client.cookies[settings.CSRF_COOKIE_NAME].value}

    def test_email_link_changes_password_once(self):
        self.client.get("/api/auth/csrf/")
        response = self.client.post(
            self.url, {"email": self.user.email}, format="json", **self.csrf_headers()
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        for line in mail.outbox[0].body.splitlines():
            if line.startswith("http"):
                reset_path = urlsplit(line).path
                break
        else:
            self.fail("Password reset email has no link.")

        response = self.client.get(reset_path)
        self.assertEqual(response.status_code, 302)
        form_path = response.url
        page = self.client.get(form_path)
        self.assertContains(page, 'name="new_password1"')
        new_password = "New-password-for-walking-53!"
        response = self.client.post(
            form_path,
            {"new_password1": new_password, "new_password2": new_password},
            format="multipart",
            **self.csrf_headers(),
        )
        self.assertRedirects(response, "/api/auth/password-reset/done/")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))
        self.assertFalse(self.client.get(reset_path).context["validlink"])

    def test_unknown_email_gets_same_response(self):
        self.client.get("/api/auth/csrf/")
        known = self.client.post(
            self.url, {"email": self.user.email}, format="json", **self.csrf_headers()
        )
        unknown = self.client.post(
            self.url, {"email": "unknown@example.com"}, format="json", **self.csrf_headers()
        )
        self.assertEqual(unknown.status_code, 200)
        self.assertEqual(unknown.data, known.data)
        self.assertEqual(len(mail.outbox), 1)

    def test_reset_requires_csrf(self):
        response = self.client.post(self.url, {"email": self.user.email}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(len(mail.outbox), 0)
