from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from .models import Category, Location


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class LocationAPITests(APITestCase):
    def test_create_and_soft_delete_location(self):
        owner = get_user_model().objects.create_user(username="walker")
        category = Category.objects.create(name="Parks")
        data = {
            "name": "City park",
            "description": "A park by the river.",
            "category": category.pk,
            "address": "Riverside Street 1",
            "latitude": "48.464717",
            "longitude": "35.046183",
        }

        url = "/api/locations/"
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 403)

        self.client.force_login(owner)
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["author"], owner.pk)

        location_id = response.data["id"]
        response = self.client.get(url)
        self.assertEqual(response.data["results"][0]["id"], location_id)

        detail_url = f"{url}{location_id}/"
        self.assertEqual(self.client.delete(detail_url).status_code, 204)
        self.assertEqual(self.client.get(detail_url).status_code, 404)
        location = Location.objects.get(pk=location_id)
        self.assertIsNotNone(location.deleted_at)
