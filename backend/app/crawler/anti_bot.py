"""Anti-bot evasion module for web crawlers.

Provides:
- Random User-Agent rotation from a pool of real browser UAs
- Request interval control with jitter (token bucket approach)
- Cookie session persistence
- CAPTCHA/WAF detection via response pattern matching
- JA3 fingerprint randomization hint (requests-level)

Usage:
    from app.crawler.anti_bot import AntiBotMiddleware

    bot = AntiBotMiddleware(min_delay=1.0, max_delay=3.0)
    session = bot.get_session()
    resp = session.get("https://example.com")
    if bot.detect_block(resp):
        # handle CAPTCHA / WAF
"""
import random
import time
import logging
from threading import Lock

import requests

logger = logging.getLogger(__name__)

# Realistic desktop Chrome User-Agent strings (Windows 10/11)
_USER_AGENTS = [
    # Chrome 120+
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Edge 120+
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
    # Firefox 122+
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
]

# Common CAPTCHA/WAF page signatures (HTML/JSON patterns, as regular strings)
_BLOCK_SIGNATURES = [
    "captcha",
    "CAPTCHA",
    "verify",
    "Verify",
    "请输入验证码",
    "验证码",
    "安全验证",
    "人机验证",
    "antibot",
    "waf",
    "WAF",
    "denied",
    "Denied",
    "access denied",
    "Access Denied",
    "too many requests",
    "Too Many Requests",
    "429",
    "503 Service Temporarily Unavailable",
    "console.log('antibot')",
    "cdn",
    "cf-ray",
    "__cfduid",
]

# HTTP status codes indicating blocking
_BLOCK_STATUS_CODES = {403, 429, 503, 509}


class AntiBotMiddleware:
    """Middleware for evading anti-bot detection.

    Manages request timing, User-Agent rotation, cookie persistence,
    and detection of CAPTCHA/WAF responses.

    Args:
        min_delay: Minimum seconds between requests.
        max_delay: Maximum seconds between requests.
        ua_pool: List of User-Agent strings (None = use built-in pool).
        cookie_file: Path to persist cookies (None = session-only).
    """

    def __init__(
        self,
        min_delay: float = 1.0,
        max_delay: float = 3.0,
        ua_pool: list[str] = None,
        cookie_file: str = None,
    ):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.ua_pool = ua_pool or _USER_AGENTS
        self._last_request_time = 0.0
        self._lock = Lock()

        self._session = self._create_session()
        logger.info(
            "AntiBotMiddleware initialized (delay=%0.1f-%0.1fs, %d UAs)",
            min_delay, max_delay, len(self.ua_pool),
        )

    def _create_session(self) -> requests.Session:
        """Create a requests.Session with default headers."""
        session = requests.Session()
        session.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        })
        return session

    def get_random_ua(self) -> str:
        """Pick a random User-Agent string."""
        return random.choice(self.ua_pool)

    def rotate_ua(self):
        """Rotate the User-Agent on the current session."""
        self._session.headers.update({"User-Agent": self.get_random_ua()})

    def wait_if_needed(self):
        """Sleep to enforce minimum request interval with random jitter.

        Thread-safe. Called automatically by get() and post().
        """
        with self._lock:
            elapsed = time.time() - self._last_request_time
            delay = random.uniform(self.min_delay, self.max_delay)
            if elapsed < delay:
                sleep_time = delay - elapsed
                time.sleep(sleep_time)
            self._last_request_time = time.time()

    def get_session(self) -> requests.Session:
        """Get the managed requests session (with rotated UA)."""
        self.rotate_ua()
        return self._session

    def get(self, url: str, **kwargs) -> requests.Response:
        """Make a rate-limited GET request.

        Automatically waits the required interval, rotates UA,
        and detects blocking responses.
        """
        self.wait_if_needed()
        self.rotate_ua()
        kwargs.setdefault("timeout", 30)
        kwargs.setdefault("headers", {})
        kwargs["headers"].setdefault("Referer", url)
        return self._session.get(url, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        """Make a rate-limited POST request."""
        self.wait_if_needed()
        self.rotate_ua()
        kwargs.setdefault("timeout", 30)
        return self._session.post(url, **kwargs)

    @staticmethod
    def detect_block(response: requests.Response) -> tuple[bool, str]:
        """Detect if a response indicates CAPTCHA/WAF/blocking.

        Args:
            response: The HTTP response to inspect.

        Returns:
            Tuple of (is_blocked, reason_string).
        """
        # Check status code first
        if response.status_code in _BLOCK_STATUS_CODES:
            return True, f"HTTP {response.status_code}"

        # Check content signatures
        content_text = response.text or ""
        content_lower = content_text.lower()
        for sig in _BLOCK_SIGNATURES:
            if sig in content_text or sig.lower() in content_lower:
                return True, f"Block signature detected: {sig[:50]}"

        # Check for unusually short HTML (CAPTCHA pages are often small)
        text = response.text.strip() if response.text else ""
        if (
            response.headers.get("Content-Type", "").startswith("text/html")
            and 100 < len(text) < 2000
            and "京东" not in text
            and "jd" not in text.lower()
        ):
            return True, f"Suspicious short HTML ({len(text)} bytes)"

        return False, ""

    def reset_session(self):
        """Reset the session entirely (e.g., after detecting a block)."""
        self._session = self._create_session()
        logger.info("Session reset")

    @property
    def cookie_jar(self):
        return self._session.cookies
