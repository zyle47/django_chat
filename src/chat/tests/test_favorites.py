import json

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from chat.models import ChatRoom, RoomFavorite


class TestRoomFavoriteModel(TestCase):
    def test_user_can_favorite_many_rooms(self):
        user = User.objects.create_user(username="alice", password="Pass123")
        for name in ("alpha", "beta", "gamma"):
            room = ChatRoom.objects.create(name=name)
            RoomFavorite.objects.create(user=user, room=room)
        self.assertEqual(RoomFavorite.objects.filter(user=user).count(), 3)

    def test_favorite_is_unique_per_user_room(self):
        user = User.objects.create_user(username="alice", password="Pass123")
        room = ChatRoom.objects.create(name="alpha")
        RoomFavorite.objects.create(user=user, room=room)
        with self.assertRaises(IntegrityError):
            RoomFavorite.objects.create(user=user, room=room)

    def test_note_defaults_empty_and_can_be_set(self):
        user = User.objects.create_user(username="alice", password="Pass123")
        room = ChatRoom.objects.create(name="alpha")
        fav = RoomFavorite.objects.create(user=user, room=room)
        self.assertEqual(fav.note, "")
        fav.note = "remember the milk"
        fav.save(update_fields=["note"])
        fav.refresh_from_db()
        self.assertEqual(fav.note, "remember the milk")


class TestToggleRoomFavoriteView(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", password="Pass123", is_active=True
        )
        self.room = ChatRoom.objects.create(name="alpha")

    def _url(self, public_id):
        return reverse("api-room-favorite", kwargs={"public_id": public_id})

    def test_requires_login(self):
        response = self.client.post(self._url(self.room.public_id))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_get_not_allowed(self):
        self.client.force_login(self.user)
        response = self.client.get(self._url(self.room.public_id))
        self.assertEqual(response.status_code, 405)

    def test_toggle_adds_then_removes_favorite(self):
        self.client.force_login(self.user)

        on = self.client.post(self._url(self.room.public_id))
        self.assertEqual(on.status_code, 200)
        self.assertTrue(json.loads(on.content)["favorited"])
        self.assertTrue(
            RoomFavorite.objects.filter(user=self.user, room=self.room).exists()
        )

        off = self.client.post(self._url(self.room.public_id))
        self.assertEqual(off.status_code, 200)
        self.assertFalse(json.loads(off.content)["favorited"])
        self.assertFalse(
            RoomFavorite.objects.filter(user=self.user, room=self.room).exists()
        )

    def test_nonexistent_room_returns_404(self):
        self.client.force_login(self.user)
        response = self.client.post(self._url("a" * 64))
        self.assertEqual(response.status_code, 404)

    def test_deleted_room_cannot_be_favorited(self):
        self.room.soft_delete()
        self.room.save(update_fields=["is_deleted", "deleted_at"])
        self.client.force_login(self.user)
        response = self.client.post(self._url(self.room.public_id))
        self.assertEqual(response.status_code, 404)


class TestSetRoomFavoriteNoteView(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", password="Pass123", is_active=True
        )
        self.room = ChatRoom.objects.create(name="alpha")
        self.favorite = RoomFavorite.objects.create(user=self.user, room=self.room)

    def _url(self, public_id):
        return reverse("api-room-favorite-note", kwargs={"public_id": public_id})

    def test_requires_login(self):
        response = self.client.post(self._url(self.room.public_id), {"note": "hi"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_get_not_allowed(self):
        self.client.force_login(self.user)
        response = self.client.get(self._url(self.room.public_id))
        self.assertEqual(response.status_code, 405)

    def test_sets_and_updates_note(self):
        self.client.force_login(self.user)

        resp = self.client.post(
            self._url(self.room.public_id), {"note": "  call mom  "}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.content)["note"], "call mom")
        self.favorite.refresh_from_db()
        self.assertEqual(self.favorite.note, "call mom")

        resp = self.client.post(self._url(self.room.public_id), {"note": "updated"})
        self.assertEqual(json.loads(resp.content)["note"], "updated")
        self.favorite.refresh_from_db()
        self.assertEqual(self.favorite.note, "updated")

    def test_blank_note_clears_it(self):
        self.favorite.note = "something"
        self.favorite.save(update_fields=["note"])
        self.client.force_login(self.user)

        resp = self.client.post(self._url(self.room.public_id), {"note": "   "})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.content)["note"], "")
        self.favorite.refresh_from_db()
        self.assertEqual(self.favorite.note, "")

    def test_note_truncated_to_200_chars(self):
        self.client.force_login(self.user)
        resp = self.client.post(self._url(self.room.public_id), {"note": "x" * 500})
        self.assertEqual(resp.status_code, 200)
        self.favorite.refresh_from_db()
        self.assertEqual(len(self.favorite.note), 200)

    def test_non_favorited_room_returns_404(self):
        other_room = ChatRoom.objects.create(name="beta")
        self.client.force_login(self.user)
        resp = self.client.post(self._url(other_room.public_id), {"note": "hi"})
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(RoomFavorite.objects.filter(room=other_room).exists())

    def test_nonexistent_room_returns_404(self):
        self.client.force_login(self.user)
        resp = self.client.post(self._url("a" * 64), {"note": "hi"})
        self.assertEqual(resp.status_code, 404)

    def test_deleted_room_returns_404(self):
        self.room.soft_delete()
        self.room.save(update_fields=["is_deleted", "deleted_at"])
        self.client.force_login(self.user)
        resp = self.client.post(self._url(self.room.public_id), {"note": "hi"})
        self.assertEqual(resp.status_code, 404)

    def test_note_is_per_user(self):
        other = User.objects.create_user(
            username="bob", password="Pass123", is_active=True
        )
        other_fav = RoomFavorite.objects.create(
            user=other, room=self.room, note="bob note"
        )
        self.client.force_login(self.user)
        self.client.post(self._url(self.room.public_id), {"note": "alice note"})
        self.favorite.refresh_from_db()
        other_fav.refresh_from_db()
        self.assertEqual(self.favorite.note, "alice note")
        self.assertEqual(other_fav.note, "bob note")


class TestIndexFavorites(TestCase):
    def test_index_marks_favorites_and_lists_them(self):
        user = User.objects.create_user(
            username="alice", password="Pass123", is_active=True
        )
        fav = ChatRoom.objects.create(name="favroom")
        ChatRoom.objects.create(name="plainroom")
        RoomFavorite.objects.create(user=user, room=fav)

        self.client.force_login(user)
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 200)

        favorites = response.context["favorites"]
        self.assertEqual([r.id for r in favorites], [fav.id])
        rooms_by_id = {r.id: r for r in response.context["rooms"]}
        self.assertTrue(rooms_by_id[fav.id].is_favorite)

    def test_index_favorites_excludes_deleted_rooms(self):
        user = User.objects.create_user(
            username="alice", password="Pass123", is_active=True
        )
        fav = ChatRoom.objects.create(name="favroom")
        RoomFavorite.objects.create(user=user, room=fav)
        fav.soft_delete()
        fav.save(update_fields=["is_deleted", "deleted_at"])

        self.client.force_login(user)
        response = self.client.get(reverse("index"))
        self.assertEqual(list(response.context["favorites"]), [])

    def test_index_attaches_and_renders_note(self):
        user = User.objects.create_user(
            username="alice", password="Pass123", is_active=True
        )
        fav = ChatRoom.objects.create(name="favroom")
        RoomFavorite.objects.create(user=user, room=fav, note="zzz-secret-note")

        self.client.force_login(user)
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 200)

        favorites = response.context["favorites"]
        self.assertEqual(favorites[0].note, "zzz-secret-note")
        self.assertIn(b"zzz-secret-note", response.content)
        # Rendered only by the favourites card (data-note attr + visible text),
        # never by the room-browser card — so exactly two occurrences.
        self.assertEqual(response.content.count(b"zzz-secret-note"), 2)

    def test_index_note_is_private_to_owner(self):
        owner = User.objects.create_user(
            username="owner", password="Pass123", is_active=True
        )
        other = User.objects.create_user(
            username="other", password="Pass123", is_active=True
        )
        room = ChatRoom.objects.create(name="favroom")
        RoomFavorite.objects.create(user=owner, room=room, note="zzz-secret-note")

        self.client.force_login(other)
        response = self.client.get(reverse("index"))
        self.assertNotIn(b"zzz-secret-note", response.content)

    def test_index_favorites_are_per_user(self):
        owner = User.objects.create_user(
            username="owner", password="Pass123", is_active=True
        )
        other = User.objects.create_user(
            username="other", password="Pass123", is_active=True
        )
        room = ChatRoom.objects.create(name="favroom")
        RoomFavorite.objects.create(user=owner, room=room)

        self.client.force_login(other)
        response = self.client.get(reverse("index"))
        self.assertEqual(list(response.context["favorites"]), [])
        rooms_by_id = {r.id: r for r in response.context["rooms"]}
        self.assertFalse(rooms_by_id[room.id].is_favorite)
