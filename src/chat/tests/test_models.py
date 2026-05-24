import hashlib

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from chat.models import ChatMessage, ChatRoom, DirectMessage, Friendship


class TestChatRoomModel(TestCase):
    def test_str(self):
        room = ChatRoom.objects.create(name="general")
        self.assertEqual(str(room), "general")

    def test_public_id_derived_from_name_on_save(self):
        room = ChatRoom.objects.create(name="hello")
        expected = hashlib.sha256("hello".encode()).hexdigest()
        self.assertEqual(room.public_id, expected)

    def test_public_id_not_overwritten_on_subsequent_save(self):
        room = ChatRoom.objects.create(name="hello")
        original = room.public_id
        room.is_deleted = True
        room.save()
        room.refresh_from_db()
        self.assertEqual(room.public_id, original)

    def test_password_hashing_round_trip(self):
        room = ChatRoom(name="secure")
        room.set_password("MyRoomPass123")
        room.save()
        self.assertTrue(room.check_password("MyRoomPass123"))
        self.assertFalse(room.check_password("WrongPass"))

    def test_check_password_without_set_password_returns_false(self):
        room = ChatRoom.objects.create(name="nopass")
        self.assertFalse(room.check_password("anything"))

    def test_set_password_stores_length(self):
        room = ChatRoom(name="length-test")
        room.set_password("twelve-chars")
        self.assertEqual(room.password_length, 12)

    def test_soft_delete_and_restore(self):
        room = ChatRoom.objects.create(name="archive")
        room.soft_delete()
        room.save(update_fields=["is_deleted", "deleted_at"])
        self.assertTrue(room.is_deleted)
        self.assertIsNotNone(room.deleted_at)

        room.restore()
        room.save(update_fields=["is_deleted", "deleted_at"])
        self.assertFalse(room.is_deleted)
        self.assertIsNone(room.deleted_at)


class TestChatMessageModel(TestCase):
    def test_str_and_room_link(self):
        room = ChatRoom.objects.create(name="support")
        msg = ChatMessage.objects.create(room=room, username="Nema", message="Hello")
        self.assertEqual(msg.room, room)
        self.assertEqual(str(msg), "Nema in support")


class TestFriendshipModel(TestCase):
    def test_sort_pair_orders_ascending(self):
        self.assertEqual(Friendship.sort_pair(5, 3), (3, 5))

    def test_sort_pair_already_ordered(self):
        self.assertEqual(Friendship.sort_pair(2, 7), (2, 7))

    def test_exists_between_returns_false_before_creation(self):
        alice = User.objects.create_user(username="alice", password="Pass123")
        bob = User.objects.create_user(username="bob", password="Pass123")
        self.assertFalse(Friendship.exists_between(alice.id, bob.id))

    def test_exists_between_returns_true_after_creation(self):
        alice = User.objects.create_user(username="alice", password="Pass123")
        bob = User.objects.create_user(username="bob", password="Pass123")
        Friendship.create_between(alice.id, bob.id)
        self.assertTrue(Friendship.exists_between(alice.id, bob.id))

    def test_exists_between_self_returns_false(self):
        alice = User.objects.create_user(username="alice", password="Pass123")
        self.assertFalse(Friendship.exists_between(alice.id, alice.id))

    def test_create_between_is_symmetric(self):
        alice = User.objects.create_user(username="alice", password="Pass123")
        bob = User.objects.create_user(username="bob", password="Pass123")
        Friendship.create_between(alice.id, bob.id)
        self.assertTrue(Friendship.exists_between(bob.id, alice.id))


class TestDirectMessageModel(TestCase):
    def test_pair_low_high_auto_set_on_save(self):
        alice = User.objects.create_user(username="alice", password="Pass123")
        bob = User.objects.create_user(username="bob", password="Pass123")
        dm = DirectMessage.objects.create(
            from_user=alice,
            to_user=bob,
            message="hi",
            expires_at=timezone.now() + timezone.timedelta(hours=1),
        )
        low, high = DirectMessage.sort_pair(alice.id, bob.id)
        self.assertEqual(dm.pair_low, low)
        self.assertEqual(dm.pair_high, high)

    def test_pair_low_high_correct_regardless_of_sender(self):
        alice = User.objects.create_user(username="alice", password="Pass123")
        bob = User.objects.create_user(username="bob", password="Pass123")
        dm = DirectMessage.objects.create(
            from_user=bob,
            to_user=alice,
            message="reply",
            expires_at=timezone.now() + timezone.timedelta(hours=1),
        )
        low, high = DirectMessage.sort_pair(alice.id, bob.id)
        self.assertEqual(dm.pair_low, low)
        self.assertEqual(dm.pair_high, high)
