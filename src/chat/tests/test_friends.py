import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from chat.models import FriendBlock, FriendRequest, Friendship
from chat.services import friends as friend_svc


class TestDMHistoryViewSecurity(TestCase):
    def test_unauthenticated_user_is_redirected_to_login(self):
        response = self.client.get(
            reverse("api-dm-history", kwargs={"peer_username": "anyone"})
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_non_friends_get_403(self):
        alice = User.objects.create_user(
            username="alice", password="Pass123", is_active=True
        )
        User.objects.create_user(username="bob", password="Pass123", is_active=True)
        self.client.force_login(alice)

        response = self.client.get(
            reverse("api-dm-history", kwargs={"peer_username": "bob"})
        )
        self.assertEqual(response.status_code, 403)

    def test_self_dm_history_returns_400(self):
        alice = User.objects.create_user(
            username="alice", password="Pass123", is_active=True
        )
        self.client.force_login(alice)

        response = self.client.get(
            reverse("api-dm-history", kwargs={"peer_username": "alice"})
        )
        self.assertEqual(response.status_code, 400)

    def test_friends_can_view_dm_history(self):
        alice = User.objects.create_user(
            username="alice", password="Pass123", is_active=True
        )
        bob = User.objects.create_user(
            username="bob", password="Pass123", is_active=True
        )
        Friendship.create_between(alice.id, bob.id)
        self.client.force_login(alice)

        response = self.client.get(
            reverse("api-dm-history", kwargs={"peer_username": "bob"})
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("messages", data)


class TestFriendListViewSecurity(TestCase):
    def test_list_friends_requires_login(self):
        response = self.client.get(reverse("api-friends-list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_list_pending_requests_requires_login(self):
        response = self.client.get(reverse("api-friends-requests"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_unread_count_requires_login(self):
        response = self.client.get(reverse("api-friends-unread-count"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_list_friends_returns_friend_data(self):
        alice = User.objects.create_user(
            username="alice", password="Pass123", is_active=True
        )
        bob = User.objects.create_user(
            username="bob", password="Pass123", is_active=True
        )
        Friendship.create_between(alice.id, bob.id)
        self.client.force_login(alice)

        response = self.client.get(reverse("api-friends-list"))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        usernames = [f["username"] for f in data["friends"]]
        self.assertIn("bob", usernames)

    def test_list_friends_includes_banned_users(self):
        alice = User.objects.create_user(
            username="alice", password="Pass123", is_active=True
        )
        bob = User.objects.create_user(
            username="bob", password="Pass123", is_active=True
        )
        FriendBlock.objects.create(blocker=alice, blocked=bob)
        self.client.force_login(alice)

        response = self.client.get(reverse("api-friends-list"))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        banned = [f for f in data["friends"] if f["banned"]]
        self.assertEqual(len(banned), 1)
        self.assertEqual(banned[0]["username"], "bob")


class TestFriendServiceLogic(TestCase):
    def test_accept_request_when_none_pending_returns_error(self):
        alice = User.objects.create_user(
            username="alice", password="Pass123", is_active=True
        )
        User.objects.create_user(username="bob", password="Pass123", is_active=True)

        result = friend_svc.accept_request(alice.id, "bob")
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "no_pending")

    def test_reject_request_when_none_pending_returns_error(self):
        alice = User.objects.create_user(
            username="alice", password="Pass123", is_active=True
        )
        User.objects.create_user(username="bob", password="Pass123", is_active=True)

        result = friend_svc.reject_request(alice.id, "bob")
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "no_pending")

    def test_send_request_to_self_is_rejected(self):
        alice = User.objects.create_user(
            username="alice", password="Pass123", is_active=True
        )

        result = friend_svc.send_request(alice.id, "alice", room_obj=None)
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "self")

    def test_blocked_user_cannot_send_friend_request(self):
        alice = User.objects.create_user(
            username="alice", password="Pass123", is_active=True
        )
        bob = User.objects.create_user(
            username="bob", password="Pass123", is_active=True
        )
        friend_svc.ban_friend(alice.id, "bob")

        result = friend_svc.send_request(bob.id, "alice", room_obj=None)
        self.assertFalse(result["ok"])
        # Blocker's existence must not be leaked to the blocked user
        self.assertEqual(result["code"], "no_such_user")

    def test_accept_request_creates_friendship(self):
        alice = User.objects.create_user(
            username="alice", password="Pass123", is_active=True
        )
        bob = User.objects.create_user(
            username="bob", password="Pass123", is_active=True
        )
        FriendRequest.objects.create(
            from_user=alice,
            to_user=bob,
            expires_at=timezone.now() + timezone.timedelta(minutes=5),
        )

        result = friend_svc.accept_request(bob.id, "alice")
        self.assertTrue(result["ok"])
        self.assertTrue(Friendship.exists_between(alice.id, bob.id))

    def test_remove_friend_tears_down_friendship(self):
        alice = User.objects.create_user(
            username="alice", password="Pass123", is_active=True
        )
        bob = User.objects.create_user(
            username="bob", password="Pass123", is_active=True
        )
        Friendship.create_between(alice.id, bob.id)

        result = friend_svc.remove_friend(alice.id, "bob")
        self.assertTrue(result["ok"])
        self.assertFalse(Friendship.exists_between(alice.id, bob.id))

    def test_remove_non_friend_returns_error(self):
        alice = User.objects.create_user(
            username="alice", password="Pass123", is_active=True
        )
        User.objects.create_user(username="bob", password="Pass123", is_active=True)

        result = friend_svc.remove_friend(alice.id, "bob")
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "not_friends")

    def test_send_request_creates_pending_request(self):
        alice = User.objects.create_user(
            username="alice", password="Pass123", is_active=True
        )
        User.objects.create_user(username="bob", password="Pass123", is_active=True)

        result = friend_svc.send_request(alice.id, "bob", room_obj=None)
        self.assertTrue(result["ok"])
        self.assertEqual(result["code"], "sent")
        self.assertTrue(FriendRequest.objects.filter(from_user=alice).exists())

    def test_send_request_when_already_pending_returns_error(self):
        alice = User.objects.create_user(
            username="alice", password="Pass123", is_active=True
        )
        User.objects.create_user(username="bob", password="Pass123", is_active=True)

        friend_svc.send_request(alice.id, "bob", room_obj=None)
        result = friend_svc.send_request(alice.id, "bob", room_obj=None)
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "already_pending")

    def test_accept_request_when_already_friends_returns_error(self):
        alice = User.objects.create_user(
            username="alice", password="Pass123", is_active=True
        )
        bob = User.objects.create_user(
            username="bob", password="Pass123", is_active=True
        )
        Friendship.create_between(alice.id, bob.id)

        result = friend_svc.accept_request(alice.id, "bob")
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "already_friends")
