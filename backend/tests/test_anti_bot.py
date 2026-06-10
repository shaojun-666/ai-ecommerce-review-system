"""Tests for the anti-bot middleware."""
import pytest
import requests
from unittest.mock import patch, MagicMock, ANY

from app.crawler.anti_bot import AntiBotMiddleware, _USER_AGENTS, _BLOCK_SIGNATURES


class TestAntiBotMiddleware:
    def make_bot(self, **kwargs):
        return AntiBotMiddleware(**kwargs)

    def _mock_response(self, status_code=200, text="", headers=None):
        resp = MagicMock(spec=requests.Response)
        resp.status_code = status_code
        resp.text = text
        resp.content = text.encode() if text else b""
        resp.headers = headers or {}
        resp.ok = 200 <= status_code < 400
        return resp

    def test_init_defaults(self):
        bot = self.make_bot()
        assert bot.min_delay == 1.0
        assert bot.max_delay == 3.0
        assert len(bot.ua_pool) > 5
        assert bot._session is not None

    def test_init_custom_delays(self):
        bot = self.make_bot(min_delay=0.5, max_delay=1.0)
        assert bot.min_delay == 0.5
        assert bot.max_delay == 1.0

    def test_get_random_ua_returns_string(self):
        bot = self.make_bot()
        ua = bot.get_random_ua()
        assert isinstance(ua, str)
        assert ua.startswith("Mozilla")

    def test_get_random_ua_is_from_pool(self):
        bot = self.make_bot()
        ua = bot.get_random_ua()
        assert ua in _USER_AGENTS

    def test_rotate_ua_changes_header(self):
        bot = self.make_bot()
        bot.rotate_ua()
        assert bot._session.headers["User-Agent"] in _USER_AGENTS

    def test_get_session_updates_ua(self):
        bot = self.make_bot()
        session = bot.get_session()
        assert session.headers["User-Agent"] in _USER_AGENTS

    def test_detect_block_status_403(self):
        bot = self.make_bot()
        resp = self._mock_response(status_code=403)
        is_blocked, reason = bot.detect_block(resp)
        assert is_blocked
        assert "403" in reason

    def test_detect_block_status_429(self):
        bot = self.make_bot()
        resp = self._mock_response(status_code=429)
        is_blocked, reason = bot.detect_block(resp)
        assert is_blocked

    def test_detect_block_captcha_signature(self):
        bot = self.make_bot()
        resp = self._mock_response(text="<html>verify captcha here</html>")
        is_blocked, reason = bot.detect_block(resp)
        assert is_blocked

    def test_detect_block_chinese_signature(self):
        bot = self.make_bot()
        resp = self._mock_response(text="<html>请输入验证码</html>")
        is_blocked, reason = bot.detect_block(resp)
        assert is_blocked

    def test_detect_block_no_block(self):
        bot = self.make_bot()
        resp = self._mock_response(
            text="<html>京东商品详情页正常内容，包含大量商品描述</html>",
            headers={"Content-Type": "text/html"},
        )
        is_blocked, reason = bot.detect_block(resp)
        assert not is_blocked

    def test_reset_session_clears_cookies(self):
        bot = self.make_bot()
        old_session = bot._session
        bot._session.cookies.set("test", "value")
        bot.reset_session()
        assert bot._session is not old_session
        assert len(bot._session.cookies) == 0

    @patch("time.sleep")
    def test_wait_if_needed_no_sleep_on_first_call(self, mock_sleep):
        bot = self.make_bot(min_delay=0.1, max_delay=0.1)
        bot.wait_if_needed()
        mock_sleep.assert_not_called()

    def test_cookie_jar_property(self):
        bot = self.make_bot()
        assert bot.cookie_jar is bot._session.cookies

    def test_get_passes_timeout(self):
        import time
        bot = self.make_bot()
        bot._last_request_time = time.time() - 10

        with patch.object(bot._session, "get") as mock_get:
            mock_get.return_value = self._mock_response(text="ok")
            bot.get("https://example.com")
            _, kwargs = mock_get.call_args
            assert kwargs.get("timeout") == 30
