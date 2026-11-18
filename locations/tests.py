from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from .models import Category, Location, LocationVisit, Review


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
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
            "address": "Riverside Street 1",
            "latitude": "48.464717",
            "longitude": "35.046183",
        }
        cls.location = Location.objects.create(
            author=cls.owner,
            category=cls.category,
            **cls.location_data,
        )
        cls.location_data["category"] = cls.category.pk
        cls.detail_url = f"/api/locations/{cls.location.pk}/"
        cls.reviews_url = f"{cls.detail_url}reviews/"

    def setUp(self):
        cache.clear()

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

    def test_review_requires_login_and_valid_rating(self):
        data = {"rating": 6, "comment": "A good place for a walk."}
        self.assertEqual(self.client.get(self.reviews_url).status_code, 200)
        self.assertEqual(self.client.post(self.reviews_url, data).status_code, 403)

        self.client.force_login(self.other_user)
        response = self.client.post(self.reviews_url, data)
        self.assertEqual(response.status_code, 400)
        self.assertIn("rating", response.data)

        data["rating"] = 5
        data["author"] = self.owner.pk
        response = self.client.post(self.reviews_url, data)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["author"], self.other_user.pk)
        self.assertEqual(response.data["location"], self.location.pk)
        self.assertEqual(self.client.post(self.reviews_url, data).status_code, 400)
        self.assertEqual(Review.objects.count(), 1)

    def test_one_vote_per_user_and_both_vote_counts(self):
        review = Review.objects.create(
            location=self.location,
            author=self.owner,
            rating=4,
            comment="Nice park.",
        )
        url = f"/api/reviews/{review.pk}/votes/"
        self.assertEqual(self.client.post(url, {"value": "like"}).status_code, 403)

        self.client.force_login(self.other_user)
        self.assertEqual(self.client.post(url, {"value": "invalid"}).status_code, 400)
        self.assertEqual(self.client.post(url, {"value": "like"}).status_code, 201)
        self.assertEqual(self.client.post(url, {"value": "dislike"}).status_code, 400)

        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(url, {"value": "dislike"}).status_code, 201)
        review_data = self.client.get(self.reviews_url).data[0]
        self.assertEqual(review_data["like_count"], 1)
        self.assertEqual(review_data["dislike_count"], 1)

        self.location.soft_delete()
        self.assertEqual(self.client.get(self.reviews_url).status_code, 404)
        self.assertEqual(self.client.post(url, {"value": "like"}).status_code, 404)

    def test_detail_counts_one_visit_per_guest_session(self):
        self.assertEqual(self.client.head(self.detail_url).status_code, 200)
        self.assertEqual(LocationVisit.objects.count(), 0)
        self.assertEqual(self.client.get(self.detail_url).data["views_last_7_days"], 1)
        self.assertEqual(self.client.get(self.detail_url).data["views_last_7_days"], 1)
        self.assertEqual(APIClient().get(self.detail_url).data["views_last_7_days"], 2)
        self.assertEqual(LocationVisit.objects.count(), 2)

    def test_detail_counts_one_visit_per_account(self):
        self.client.force_login(self.owner)
        second_browser = APIClient()
        second_browser.force_login(self.owner)
        self.assertEqual(self.client.get(self.detail_url).data["views_last_7_days"], 1)
        self.assertEqual(second_browser.get(self.detail_url).data["views_last_7_days"], 1)

        cache.delete(f"location-visit:{self.location.pk}:user:{self.owner.pk}")
        self.assertEqual(self.client.get(self.detail_url).data["views_last_7_days"], 2)

    def test_list_calculates_popularity_from_reviews_and_recent_visits(self):
        Review.objects.create(location=self.location, author=self.owner, rating=5, comment="Great.")
        Review.objects.create(
            location=self.location, author=self.other_user, rating=3, comment="Fine."
        )
        LocationVisit.objects.create(location=self.location)
        LocationVisit.objects.create(location=self.location)
        LocationVisit.objects.create(location=self.location)
        old_visit = LocationVisit.objects.create(location=self.location)
        LocationVisit.objects.filter(pk=old_visit.pk).update(
            created_at=timezone.now() - timedelta(days=8),
        )

        response = self.client.get("/api/locations/")
        self.assertEqual(response.status_code, 200)
        location = response.data[0]
        self.assertEqual(location["rating"], 4)
        self.assertEqual(location["review_count"], 2)
        self.assertEqual(location["views_last_7_days"], 3)
        self.assertEqual(location["popularity"], 13)
        self.assertEqual(LocationVisit.objects.count(), 4)
