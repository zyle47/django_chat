from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, TestCase

from chat.http.views.admin_users import set_user_level
from chat.models import UpgradeRequest, UserProfile


def _attach_session_and_messages(request):
    """Attach a session and messages storage to a RequestFactory request."""
    session = SessionStore()
    session.save()
    request.session = session
    request._messages = FallbackStorage(request)


class TestSetUserLevel(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.superuser = User.objects.create_superuser(
            username="admin", password="Pass123", email="admin@test.com"
        )
        self.target = User.objects.create_user(username="alice", password="Pass123")
        # profile is auto-created (bronze by default)

    def test_set_level_changes_profile(self):
        request = self.factory.post(
            "/fake/set-level/",
            {"level": "gold", "redirect_query": "", "redirect_sort": "-date_joined"},
        )
        request.user = self.superuser
        _attach_session_and_messages(request)

        response = set_user_level(request, self.target.id)

        self.assertEqual(response.status_code, 302)
        self.target.refresh_from_db()
        self.assertEqual(self.target.profile.level, "gold")

    def test_set_level_marks_pending_upgrade_request_handled(self):
        req = UpgradeRequest.objects.create(
            user=self.target, requested_level="gold", handled=False
        )

        request = self.factory.post(
            "/fake/set-level/",
            {"level": "gold", "redirect_query": "", "redirect_sort": "-date_joined"},
        )
        request.user = self.superuser
        _attach_session_and_messages(request)

        set_user_level(request, self.target.id)

        req.refresh_from_db()
        self.assertTrue(req.handled)

    def test_set_level_creates_profile_if_missing(self):
        # Delete the auto-created profile to simulate pre-migration user
        UserProfile.objects.filter(user=self.target).delete()

        request = self.factory.post(
            "/fake/set-level/",
            {"level": "silver", "redirect_query": "", "redirect_sort": "-date_joined"},
        )
        request.user = self.superuser
        _attach_session_and_messages(request)

        set_user_level(request, self.target.id)

        profile = UserProfile.objects.get(user=self.target)
        self.assertEqual(profile.level, "silver")

    def test_invalid_level_does_not_change_profile(self):
        original_level = self.target.profile.level

        request = self.factory.post(
            "/fake/set-level/",
            {"level": "diamond", "redirect_query": "", "redirect_sort": "-date_joined"},
        )
        request.user = self.superuser
        _attach_session_and_messages(request)

        response = set_user_level(request, self.target.id)

        self.assertEqual(response.status_code, 302)
        self.target.refresh_from_db()
        self.assertEqual(self.target.profile.level, original_level)

    def test_non_superuser_is_denied(self):
        regular_user = User.objects.create_user(
            username="regular", password="Pass123", is_active=True
        )

        request = self.factory.post(
            "/fake/set-level/",
            {"level": "gold", "redirect_query": "", "redirect_sort": "-date_joined"},
        )
        request.user = regular_user
        _attach_session_and_messages(request)

        from django.core.exceptions import PermissionDenied

        with self.assertRaises(PermissionDenied):
            set_user_level(request, self.target.id)

    def test_only_pending_requests_are_marked_handled(self):
        already_handled = UpgradeRequest.objects.create(
            user=self.target, requested_level="silver", handled=True
        )
        pending = UpgradeRequest.objects.create(
            user=self.target, requested_level="gold", handled=False
        )

        request = self.factory.post(
            "/fake/set-level/",
            {"level": "gold", "redirect_query": "", "redirect_sort": "-date_joined"},
        )
        request.user = self.superuser
        _attach_session_and_messages(request)

        set_user_level(request, self.target.id)

        pending.refresh_from_db()
        already_handled.refresh_from_db()
        self.assertTrue(pending.handled)
        # already-handled row stays handled (it was True already; just confirm no regression)
        self.assertTrue(already_handled.handled)
