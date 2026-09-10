from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from dron_map.models import Projects


class DronMapPageRenderingTests(TestCase):
    def setUp(self):
        # Without this the client re-raises NoReverseMatch instead of reporting
        # the 500 a real visitor would receive.
        self.client = Client(raise_request_exception=False)
        self.user = User.objects.create_user(username="owner", password="password")
        self.project = Projects.objects.create(
            Farm="Owner Farm",
            Field="Parsel A",
            Title="Owner Project",
            State="Active",
            created_by=self.user,
        )
        self.client.force_login(self.user)

    def test_project_list_renders(self):
        response = self.client.get(reverse("dron_map:projects"))
        self.assertEqual(response.status_code, 200)

    def test_project_map_renders(self):
        response = self.client.get(reverse("dron_map:map", args=[self.project.id]))
        self.assertEqual(response.status_code, 200)
