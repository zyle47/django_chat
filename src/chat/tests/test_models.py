from django.test import TestCase

from chat.models import ChatMessage, ChatRoom


class TestChatModels(TestCase):
    def test_chat_room_str(self):
        room = ChatRoom.objects.create(name="general")
        self.assertEqual(str(room), "general")

    def test_chat_message_is_linked_to_room(self):
        room = ChatRoom.objects.create(name="support")
        msg = ChatMessage.objects.create(room=room, username="Nema", message="Hello")
        self.assertEqual(msg.room, room)
        self.assertEqual(str(msg), "Nema in support")

    def test_room_password_hashing(self):
        room = ChatRoom(name="secure")
        room.set_password("MyRoomPass123")
        room.save()
        self.assertTrue(room.check_password("MyRoomPass123"))
        self.assertFalse(room.check_password("WrongPass"))

    def test_soft_delete_and_restore_room(self):
        room = ChatRoom.objects.create(name="archive")
        room.soft_delete()
        room.save(update_fields=["is_deleted", "deleted_at"])
        self.assertTrue(room.is_deleted)
        self.assertIsNotNone(room.deleted_at)

        room.restore()
        room.save(update_fields=["is_deleted", "deleted_at"])
        self.assertFalse(room.is_deleted)
        self.assertIsNone(room.deleted_at)
