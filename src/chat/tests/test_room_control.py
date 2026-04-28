from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from chat.models import ChatRoom


class TestRoomControlViews(TestCase):
    def test_superadmin_only_room_control_forbidden_for_regular_user(self):
        regular_user = User.objects.create_user(username="regular", password="StrongPass123", is_active=True)
        self.client.force_login(regular_user)

        response = self.client.get(reverse("admin-room-control-list"))
        self.assertEqual(response.status_code, 403)

    def test_superadmin_can_search_and_sort_rooms(self):
        superadmin = User.objects.create_superuser(username="root", password="StrongPass123", email="root@test.com")
        ChatRoom.objects.create(name="general")
        ChatRoom.objects.create(name="support")

        self.client.force_login(superadmin)
        response = self.client.get(reverse("admin-room-control-list"), {"q": "general", "sort": "name"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "general")
        self.assertNotContains(response, "support")

    def test_superadmin_can_soft_delete_and_restore_room(self):
        superadmin = User.objects.create_superuser(username="root", password="StrongPass123", email="root@test.com")
        room = ChatRoom.objects.create(name="team")

        self.client.force_login(superadmin)
        delete_response = self.client.post(
            reverse("admin-room-set-deleted", kwargs={"room_id": room.id}),
            {"is_deleted": "1", "redirect_query": "", "redirect_sort": "-created_at"},
        )
        self.assertEqual(delete_response.status_code, 302)
        room.refresh_from_db()
        self.assertTrue(room.is_deleted)
        self.assertIsNotNone(room.deleted_at)

        restore_response = self.client.post(
            reverse("admin-room-set-deleted", kwargs={"room_id": room.id}),
            {"is_deleted": "0", "redirect_query": "", "redirect_sort": "-created_at"},
        )
        self.assertEqual(restore_response.status_code, 302)
        room.refresh_from_db()
        self.assertFalse(room.is_deleted)
        self.assertIsNone(room.deleted_at)
