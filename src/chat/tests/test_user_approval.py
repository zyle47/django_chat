from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class TestUserApprovalViews(TestCase):
    def test_superadmin_only_page_forbidden_for_regular_user(self):
        regular_user = User.objects.create_user(username="regular", password="StrongPass123", is_active=True)
        self.client.force_login(regular_user)

        response = self.client.get(reverse("admin-user-approval-list"))
        self.assertEqual(response.status_code, 403)

    def test_superadmin_can_search_and_sort_users(self):
        superadmin = User.objects.create_superuser(username="root", password="StrongPass123", email="root@test.com")
        User.objects.create_user(username="alpha", password="StrongPass123", is_active=False)
        User.objects.create_user(username="bravo", password="StrongPass123", is_active=True)

        self.client.force_login(superadmin)
        response = self.client.get(reverse("admin-user-approval-list"), {"q": "alpha", "sort": "username"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "alpha")
        self.assertNotContains(response, "bravo")

    def test_superadmin_can_activate_user(self):
        superadmin = User.objects.create_superuser(username="root", password="StrongPass123", email="root@test.com")
        pending_user = User.objects.create_user(username="pending", password="StrongPass123", is_active=False)

        self.client.force_login(superadmin)
        response = self.client.post(
            reverse("admin-user-set-active", kwargs={"user_id": pending_user.id}),
            {"is_active": "1", "redirect_query": "", "redirect_sort": "-date_joined"},
        )

        self.assertEqual(response.status_code, 302)
        pending_user.refresh_from_db()
        self.assertTrue(pending_user.is_active)

    def test_superadmin_cannot_deactivate_self(self):
        superadmin = User.objects.create_superuser(username="root", password="StrongPass123", email="root@test.com")
        self.client.force_login(superadmin)

        response = self.client.post(
            reverse("admin-user-set-active", kwargs={"user_id": superadmin.id}),
            {"is_active": "0", "redirect_query": "", "redirect_sort": "-date_joined"},
        )

        self.assertEqual(response.status_code, 302)
        superadmin.refresh_from_db()
        self.assertTrue(superadmin.is_active)
