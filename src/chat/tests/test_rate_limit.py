from django.test import TestCase

from chat.services.rate_limit import is_rate_limited


class TestRateLimitService(TestCase):
    def test_first_request_is_not_limited(self):
        self.assertFalse(is_rate_limited("rl:t1", limit=3, window=60))

    def test_requests_up_to_limit_are_all_allowed(self):
        key = "rl:t2"
        results = [is_rate_limited(key, limit=3, window=60) for _ in range(3)]
        self.assertFalse(any(results))

    def test_request_over_limit_is_blocked(self):
        key = "rl:t3"
        for _ in range(3):
            is_rate_limited(key, limit=3, window=60)
        self.assertTrue(is_rate_limited(key, limit=3, window=60))

    def test_different_keys_are_independent(self):
        for _ in range(10):
            is_rate_limited("rl:A", limit=3, window=60)
        self.assertFalse(is_rate_limited("rl:B", limit=3, window=60))

    def test_limit_of_one_blocks_on_second_call(self):
        key = "rl:t4"
        self.assertFalse(is_rate_limited(key, limit=1, window=60))
        self.assertTrue(is_rate_limited(key, limit=1, window=60))
