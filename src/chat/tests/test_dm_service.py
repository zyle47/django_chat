from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from chat.models import DirectMessage, DMRead, Friendship
from chat.services import dm as dm_svc


def _user(username):
    return User.objects.create_user(
        username=username, password="Pass123", is_active=True
    )


def _dm(sender, recipient, minutes_ago=0):
    now = timezone.now()
    dm = DirectMessage.objects.create(
        from_user=sender,
        to_user=recipient,
        message=f"{sender.username}→{recipient.username}",
        expires_at=now + timezone.timedelta(hours=1),
    )
    if minutes_ago:
        DirectMessage.objects.filter(id=dm.id).update(
            created_at=now - timezone.timedelta(minutes=minutes_ago)
        )
    return dm


class TestMarkRead(TestCase):
    def test_creates_dmread_entry(self):
        alice = _user("alice")
        bob = _user("bob")
        dm_svc.mark_read(alice.id, bob.id)
        self.assertTrue(DMRead.objects.filter(user=alice, peer=bob).exists())

    def test_second_call_updates_not_duplicates(self):
        alice = _user("alice")
        bob = _user("bob")
        dm_svc.mark_read(alice.id, bob.id)
        dm_svc.mark_read(alice.id, bob.id)
        self.assertEqual(DMRead.objects.filter(user=alice, peer=bob).count(), 1)


class TestUnreadCountsByPeer(TestCase):
    def test_no_messages_returns_empty_dict(self):
        alice = _user("alice")
        self.assertEqual(dm_svc.unread_counts_by_peer(alice.id), {})

    def test_unread_message_is_counted(self):
        alice = _user("alice")
        bob = _user("bob")
        _dm(bob, alice)
        counts = dm_svc.unread_counts_by_peer(alice.id)
        self.assertEqual(counts.get(bob.id), 1)

    def test_multiple_messages_from_same_peer_are_summed(self):
        alice = _user("alice")
        bob = _user("bob")
        _dm(bob, alice)
        _dm(bob, alice)
        counts = dm_svc.unread_counts_by_peer(alice.id)
        self.assertEqual(counts.get(bob.id), 2)

    def test_read_messages_are_not_counted(self):
        alice = _user("alice")
        bob = _user("bob")
        _dm(bob, alice, minutes_ago=5)
        dm_svc.mark_read(alice.id, bob.id)
        counts = dm_svc.unread_counts_by_peer(alice.id)
        self.assertEqual(counts.get(bob.id, 0), 0)

    def test_sent_messages_are_not_counted_for_sender(self):
        alice = _user("alice")
        bob = _user("bob")
        _dm(alice, bob)
        counts = dm_svc.unread_counts_by_peer(alice.id)
        self.assertEqual(counts.get(bob.id, 0), 0)


class TestUnreadConversationCount(TestCase):
    def test_no_friendships_returns_zero(self):
        alice = _user("alice")
        self.assertEqual(dm_svc.unread_conversation_count(alice.id), 0)

    def test_unread_dm_from_friend_counts_as_one_conversation(self):
        alice = _user("alice")
        bob = _user("bob")
        Friendship.create_between(alice.id, bob.id)
        _dm(bob, alice)
        self.assertEqual(dm_svc.unread_conversation_count(alice.id), 1)

    def test_multiple_unread_from_same_friend_counts_as_one_conversation(self):
        alice = _user("alice")
        bob = _user("bob")
        Friendship.create_between(alice.id, bob.id)
        _dm(bob, alice)
        _dm(bob, alice)
        self.assertEqual(dm_svc.unread_conversation_count(alice.id), 1)

    def test_after_reading_count_drops_to_zero(self):
        alice = _user("alice")
        bob = _user("bob")
        Friendship.create_between(alice.id, bob.id)
        _dm(bob, alice, minutes_ago=5)
        dm_svc.mark_read(alice.id, bob.id)
        self.assertEqual(dm_svc.unread_conversation_count(alice.id), 0)

    def test_two_friends_with_unread_counts_as_two_conversations(self):
        alice = _user("alice")
        bob = _user("bob")
        carol = _user("carol")
        Friendship.create_between(alice.id, bob.id)
        Friendship.create_between(alice.id, carol.id)
        _dm(bob, alice)
        _dm(carol, alice)
        self.assertEqual(dm_svc.unread_conversation_count(alice.id), 2)
