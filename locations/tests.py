from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .models import Category, Location


class LocationAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.owner = user_model.objects.create_user(username="owner")
        cls.other_user = user_model.objects.create_user(username="visitor")
        cls.admin = user_model.objects.create_user(username="admin", is_staff=True)
        cls.category = Category.objects.create(name="Parks")
        cls.location_data = {
            "name": "City park",
            "description": "A park by the river.",
            "category": cls.category.pk,
            "address": "Riverside Street 1",
            "latitude": "48.464717",
            "longitude": "35.046183",
        }
        cls.location = Location.objects.create(
            author=cls.owner,
            category=cls.category,
            **{key: value for key, value in cls.location_data.items() if key != "category"},
        )
        cls.detail_url = f"/api/locations/{cls.location.pk}/"

    def test_guest_can_read_but_cannot_create(self):
        self.assertEqual(self.client.get("/api/locations/").status_code, 200)
        self.assertEqual(self.client.get(self.detail_url).status_code, 200)
        response = self.client.post("/api/locations/", self.location_data, format="json")
        self.assertEqual(response.status_code, 403)

    def test_create_uses_the_session_user_as_author(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            "/api/locations/",
            {**self.location_data, "author": self.other_user.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["author"], self.owner.pk)

    def test_edit_requires_owner_or_admin(self):
        self.client.force_login(self.other_user)
        response = self.client.patch(self.detail_url, {"name": "New name"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.delete(self.detail_url).status_code, 403)

        self.client.force_login(self.admin)
        response = self.client.patch(self.detail_url, {"name": "New name"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.location.refresh_from_db()
        self.assertEqual(self.location.name, "New name")

    def test_deleted_location_remains_in_database_and_disappears_from_api(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.delete(self.detail_url).status_code, 204)
        self.location.refresh_from_db()
        self.assertIsNotNone(self.location.deleted_at)
        self.assertEqual(self.client.get(self.detail_url).status_code, 404)
        self.assertEqual(self.client.get("/api/locations/").data, [])

    def test_category_access_and_deletion(self):
        url = "/api/categories/"
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(url, {"name": "Museums"}).status_code, 403)

        self.client.force_login(self.admin)
        response = self.client.post(url, {"name": "Museums"}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        detail_url = f"{url}{response.data['id']}/"
        self.assertEqual(self.client.patch(detail_url, {"name": "Exhibitions"}).status_code, 200)
        self.assertEqual(self.client.delete(detail_url).status_code, 204)
        self.assertEqual(self.client.delete(f"{url}{self.category.pk}/").status_code, 409)
