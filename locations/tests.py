from csv import DictReader
from datetime import timedelta
from io import StringIO

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

    def create_location(self, name, category, author, description="A place to visit."):
        return Location.objects.create(
            name=name,
            description=description,
            category=category,
            address="Main street 1",
            latitude="48.464717",
            longitude="35.046183",
            author=author,
        )

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
        self.assertEqual(self.client.get("/api/locations/").data["results"], [])

    def test_category_access_and_deletion(self):
        url = "/api/categories/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["id"], self.category.pk)
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
        review_data = self.client.get(self.reviews_url).data["results"][0]
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
        location = response.data["results"][0]
        self.assertEqual(location["rating"], 4)
        self.assertEqual(location["review_count"], 2)
        self.assertEqual(location["views_last_7_days"], 3)
        self.assertEqual(location["popularity"], 13)
        self.assertEqual(LocationVisit.objects.count(), 4)

    def test_location_search_filters_and_ordering(self):
        museums = Category.objects.create(name="Museums")
        museum = self.create_location(
            "City museum", museums, self.other_user, "See the photo exhibit."
        )
        Review.objects.create(location=museum, author=self.owner, rating=5, comment="Nice museum.")
        Review.objects.create(
            location=self.location, author=self.owner, rating=3, comment="Fine park."
        )
        for _ in range(5):
            LocationVisit.objects.create(location=self.location)

        url = "/api/locations/"
        response = self.client.get(url, {"search": "photo"})
        self.assertEqual(response.data["results"][0]["id"], museum.pk)
        self.assertEqual(response.data["count"], 1)

        filters = {
            "search": "park",
            "category": self.category.pk,
            "author": self.owner.pk,
            "rating": 3,
        }
        response = self.client.get(url, filters)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.location.pk)
        filters["rating"] = 5
        self.assertEqual(self.client.get(url, filters).data["count"], 0)

        for ordering, first_id in (
            ("created_at", self.location.pk),
            ("-created_at", museum.pk),
            ("-rating", museum.pk),
            ("-popularity", self.location.pk),
        ):
            response = self.client.get(url, {"ordering": ordering})
            self.assertEqual(response.data["results"][0]["id"], first_id)

    def test_location_pages_have_stable_order_for_equal_ratings(self):
        for number in range(11):
            self.create_location(f"Park {number}", self.category, self.owner)

        url = "/api/locations/"
        first = self.client.get(url, {"ordering": "rating"})
        second = self.client.get(first.data["next"])

        self.assertEqual(first.data["count"], 12)
        self.assertEqual(len(first.data["results"]), 10)
        self.assertEqual(first.data["results"][0]["name"], "Park 10")
        self.assertEqual(len(second.data["results"]), 2)
        self.assertEqual(second.data["results"][-1]["id"], self.location.pk)
        self.assertIsNone(second.data["next"])

    def test_location_list_cache_refreshes_after_writes(self):
        url = "/api/locations/"
        first = self.client.get(url)
        self.assertEqual(first.data["results"][0]["name"], "City park")
        self.location.name = "Updated directly"
        self.location.save(update_fields=["name"])
        cached = self.client.get(url)
        self.assertEqual(cached.data["results"][0]["name"], "City park")

        self.client.force_login(self.owner)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(url, self.location_data, format="json")
        self.assertEqual(response.status_code, 201)
        new_location_id = response.data["id"]
        self.assertEqual(self.client.get(url).data["count"], 2)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch(self.detail_url, {"name": "Updated in API"})
        self.assertEqual(response.status_code, 200)
        updated = self.client.get(url, {"search": "Updated in API"})
        self.assertEqual(updated.data["results"][0]["name"], "Updated in API")

        self.assertEqual(self.client.get(url, {"rating": 5}).data["count"], 0)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.reviews_url, {"rating": 5, "comment": "Nice park."})
        self.assertEqual(response.status_code, 201)
        rated = self.client.get(url, {"rating": 5})
        self.assertEqual(rated.data["results"][0]["rating"], 5)

        with self.captureOnCommitCallbacks(execute=True):
            self.client.get(self.detail_url)
        visited = self.client.get(url, {"rating": 5})
        self.assertEqual(visited.data["results"][0]["views_last_7_days"], 1)

        self.assertEqual(self.client.get(url).data["count"], 2)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete(f"{url}{new_location_id}/")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.get(url).data["count"], 1)

    def test_export_json_applies_filters_to_all_locations(self):
        for number in range(11):
            self.create_location(f"Park {number}", self.category, self.owner)

        museums = Category.objects.create(name="Museums")
        self.create_location("Museum park", museums, self.other_user)
        self.location.soft_delete()

        response = self.client.get(
            "/api/locations/export/",
            {"category": self.category.pk, "ordering": "created_at", "page": 2},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Disposition"], 'attachment; filename="locations.json"')
        locations = response.json()
        self.assertEqual(len(locations), 11)
        self.assertEqual(locations[0]["name"], "Park 0")
        self.assertEqual(locations[-1]["name"], "Park 10")

    def test_export_csv_preserves_unicode_and_writes_formula_as_text(self):
        self.location.name = "Парк, Дніпро"
        self.location.description = '  =1+1\r\nРядок з "лапками"'
        self.location.save()

        response = self.client.get("/api/locations/export/", {"file_type": "csv"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertEqual(response["Content-Disposition"], 'attachment; filename="locations.csv"')
        csv_data = response.content.decode("utf-8")
        rows = list(DictReader(StringIO(csv_data, newline="")))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], self.location.name)
        self.assertEqual(rows[0]["description"], "'" + self.location.description)
        self.assertEqual(rows[0]["latitude"], "48.464717")

    def test_empty_csv_keeps_columns_and_invalid_format_returns_400(self):
        url = "/api/locations/export/"
        response = self.client.get(url, {"file_type": "csv", "search": "missing location"})
        self.assertEqual(response.status_code, 200)
        csv_data = response.content.decode("utf-8")
        rows = DictReader(StringIO(csv_data))
        self.assertIn("name", rows.fieldnames)
        self.assertIn("popularity", rows.fieldnames)
        self.assertEqual(list(rows), [])

        response = self.client.get(url, {"file_type": "xml"})
        self.assertEqual(response.status_code, 400)
