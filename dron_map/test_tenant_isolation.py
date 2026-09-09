from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from dron_map.models import Projects


class ProjectAggregateTenantIsolationTests(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="password")
        self.bob = User.objects.create_user(username="bob", password="password")
        self.carol = User.objects.create_user(username="carol", password="password")

        self.alice_project = Projects.objects.create(
            Farm="Kuzey Bahce",
            Field="Parsel A",
            Title="Alice Project",
            State="Hasat",
            created_by=self.alice,
        )

        self.bob_project = Projects.objects.create(
            Farm="Guney Bahce",
            Field="Parsel B",
            Title="Bob Project",
            State="Sulama",
            created_by=self.bob,
        )

    def test_list_does_not_leak_across_users(self):
        self.client.force_authenticate(user=self.bob)
        response = self.client.get("/api/projects/")
        rows = response.data["results"]
        ids = [row["id"] for row in rows]
        self.assertIn(self.bob_project.id, ids)
        self.assertNotIn(self.alice_project.id, ids)
        self.assertNotIn("Kuzey Bahce", [row["Farm"] for row in rows])

    def test_by_farm_does_not_leak_across_users(self):
        self.client.force_authenticate(user=self.bob)
        response = self.client.get("/api/projects/by_farm/")
        groups = response.data
        self.assertNotIn("Kuzey Bahce", [group["farm"] for group in groups])
        nested_ids = [
            project["id"] for group in groups for project in group["projects"]
        ]
        self.assertNotIn(self.alice_project.id, nested_ids)

    def test_by_state_does_not_leak_across_users(self):
        self.client.force_authenticate(user=self.bob)
        response = self.client.get("/api/projects/by_state/")
        rows = list(response.data)
        self.assertNotIn("Hasat", [row["State"] for row in rows])
        self.assertEqual([row["State"] for row in rows], ["Sulama"])
        bob_rows = [row for row in rows if row["State"] == "Sulama"]
        self.assertEqual([row["project_count"] for row in bob_rows], [1])

    def test_statistics_counts_only_own_projects(self):
        self.client.force_authenticate(user=self.bob)
        response = self.client.get("/api/projects/statistics/")
        stats = response.data
        self.assertEqual(stats["total_projects"], 1)
        self.assertEqual(stats["total_farms"], 1)
        self.assertEqual(stats["total_fields"], 1)
        self.assertEqual(
            [row["State"] for row in stats["projects_by_state"]], ["Sulama"]
        )

    def test_statistics_empty_for_user_without_projects(self):
        self.client.force_authenticate(user=self.carol)
        response = self.client.get("/api/projects/statistics/")
        stats = response.data
        self.assertEqual(stats["total_projects"], 0)
        self.assertEqual(stats["total_farms"], 0)
        self.assertEqual(stats["total_fields"], 0)
        self.assertEqual(list(stats["projects_by_state"]), [])
