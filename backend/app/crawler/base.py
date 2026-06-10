"""Crawler base class with strategy pattern.

Subclasses implement platform-specific page parsing (extract_product, extract_reviews).
The base class handles HTTP requests, retry with exponential backoff, anti-bot detection,
and structured result formatting.

Extends:
    BaseCrawler  — implement extract_product() and extract_reviews()
"""
import random
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from app.crawler.anti_bot import AntiBotMiddleware

logger = logging.getLogger(__name__)


class CrawlerError(Exception):
    """Base crawler exception."""
    pass


class CrawlerTimeoutError(CrawlerError):
    """Request timed out."""
    pass


class CrawlerBlockedError(CrawlerError):
    """Request was blocked by anti-bot."""
    pass


class EmptyResponseError(CrawlerError):
    """Response contained no usable data."""
    pass


class ExtractionError(CrawlerError):
    """Failed to parse expected fields from response."""
    pass


class PageNotFoundError(CrawlerError):
    """Target page returned 404."""
    pass


@dataclass
class CrawlerResult:
    """Structured result from a crawl operation."""
    product: Optional[dict] = None
    reviews: list[dict] = field(default_factory=list)
    total_pages: int = 0
    current_page: int = 0
    items_found: int = 0
    error: Optional[str] = None
    blocked: bool = False


class BaseCrawler(ABC):
    """Abstract base class for platform-specific crawlers.

    Args:
        platform: Platform name (e.g., "jd", "taobao").
        min_delay: Minimum seconds between requests.
        max_delay: Maximum seconds between requests.
        max_retries: Maximum retry attempts per request.
        retry_base_delay: Base delay in seconds for exponential backoff.
    """

    def __init__(
        self,
        platform: str = "unknown",
        min_delay: float = 1.0,
        max_delay: float = 3.0,
        max_retries: int = 3,
        retry_base_delay: float = 2.0,
    ):
        self.platform = platform
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.anti_bot = AntiBotMiddleware(min_delay=min_delay, max_delay=max_delay)
        logger.info("Initialized %s crawler", platform)

    @abstractmethod
    def extract_product(self, url: str, html: str) -> dict:
        """Parse product detail from HTML.

        Returns: dict with keys like name, price, platform_product_id.
        """
        ...

    @abstractmethod
    def extract_reviews(self, url: str, html: str, page: int = 1) -> list[dict]:
        """Parse review list from HTML/JSON.

        Returns: list of dicts with content, rating, author_name, created_at, etc.
        """
        ...

    @abstractmethod
    def get_review_url(self, product_url: str, page: int = 1) -> str:
        """Build the URL for fetching reviews of a given product page."""
        ...

    def crawl_product(self, url: str) -> CrawlerResult:
        """Crawl product details from a URL with retry and backoff.

        Args:
            url: Product page URL.

        Returns:
            CrawlerResult with product dict or error.
        """
        html = self._fetch_with_retry(url)
        if html is None:
            return CrawlerResult(error=f"Failed to fetch {url} after {self.max_retries} retries")

        try:
            product = self.extract_product(url, html)
            return CrawlerResult(product=product, items_found=1)
        except Exception as e:
            logger.error("Failed to extract product from %s: %s", url, e)
            return CrawlerResult(error=f"Extraction failed: {e}")

    def crawl_reviews(self, product_url: str, page: int = 1) -> CrawlerResult:
        """Crawl reviews for a product page with retry.

        Args:
            product_url: Product page URL.
            page: Review page number.

        Returns:
            CrawlerResult with review list or error.
        """
        review_url = self.get_review_url(product_url, page)
        html = self._fetch_with_retry(review_url)
        if html is None:
            return CrawlerResult(
                error=f"Failed to fetch reviews for page {page}",
                current_page=page,
            )

        try:
            reviews = self.extract_reviews(product_url, html, page)
            return CrawlerResult(
                reviews=reviews,
                current_page=page,
                total_pages=self._estimate_total_pages(html),
                items_found=len(reviews),
            )
        except Exception as e:
            logger.error("Failed to extract reviews (page %d): %s", page, e)
            return CrawlerResult(
                error=f"Review extraction failed: {e}",
                current_page=page,
            )

    def crawl_all(self, product_url: str, page_limit: int = 5) -> CrawlerResult:
        """Crawl product details and all available review pages.

        Args:
            product_url: Product page URL.
            page_limit: Maximum number of review pages to crawl.

        Returns:
            Aggregated CrawlerResult with product + all reviews.
        """
        # Crawl product first
        product_result = self.crawl_product(product_url)
        all_reviews = []
        total_found = 0
        first_page_result = None

        for page in range(1, page_limit + 1):
            result = self.crawl_reviews(product_url, page)
            if first_page_result is None:
                first_page_result = result
            if result.error:
                if page == 1:
                    return CrawlerResult(
                        product=product_result.product,
                        error=result.error,
                        blocked=result.blocked,
                    )
                break
            all_reviews.extend(result.reviews)
            total_found += result.items_found
            # Stop if fewer results than expected (last page)
            if len(result.reviews) < 10:
                break

        return CrawlerResult(
            product=product_result.product,
            reviews=all_reviews,
            total_pages=first_page_result.total_pages if first_page_result else page_limit,
            current_page=page_limit,
            items_found=total_found,
        )

    def _fetch_with_retry(self, url: str) -> Optional[str]:
        """Fetch a URL with exponential backoff retry.

        Returns HTML text on success, None on failure after exhausting retries.
        """
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.anti_bot.get(url)

                # Detect blocking
                is_blocked, reason = self.anti_bot.detect_block(resp)
                if is_blocked:
                    logger.warning("Request blocked (attempt %d/%d): %s — %s", attempt, self.max_retries, url, reason)
                    if attempt < self.max_retries:
                        self.anti_bot.reset_session()
                        self._backoff(attempt)
                        continue
                    raise CrawlerBlockedError(f"Blocked after {self.max_retries} retries: {reason}")

                # Handle 404
                if resp.status_code == 404:
                    raise PageNotFoundError(f"Page not found: {url}")

                # Handle other errors
                if resp.status_code != 200:
                    logger.warning("HTTP %d (attempt %d/%d): %s", resp.status_code, attempt, self.max_retries, url)
                    if attempt < self.max_retries:
                        self._backoff(attempt)
                        continue
                    raise CrawlerError(f"HTTP {resp.status_code} after {self.max_retries} retries")

                # Check for empty response
                if not resp.text or len(resp.text.strip()) < 50:
                    logger.warning("Empty/short response (attempt %d/%d): %s", attempt, self.max_retries, url)
                    if attempt < self.max_retries:
                        self._backoff(attempt)
                        continue
                    raise EmptyResponseError(f"Empty response after {self.max_retries} retries")

                return resp.text

            except CrawlerBlockedError:
                raise
            except PageNotFoundError:
                raise
            except requests.exceptions.Timeout as e:
                last_error = CrawlerTimeoutError(f"Request timed out (attempt {attempt}): {e}")
                logger.warning("Timeout (attempt %d/%d): %s", attempt, self.max_retries, url)
                if attempt < self.max_retries:
                    self._backoff(attempt)
            except requests.exceptions.RequestException as e:
                last_error = CrawlerError(f"Request failed (attempt {attempt}): {e}")
                logger.warning("Request failed (attempt %d/%d): %s", attempt, self.max_retries, url)
                if attempt < self.max_retries:
                    self._backoff(attempt)
            except Exception as e:
                last_error = CrawlerError(f"Unexpected error (attempt {attempt}): {e}")
                logger.error("Unexpected error fetching %s: %s", url, e)
                if attempt < self.max_retries:
                    self._backoff(attempt)

        logger.error("All %d retries exhausted for %s: %s", self.max_retries, url, last_error)
        return None

    def _backoff(self, attempt: int):
        """Exponential backoff with jitter."""
        delay = self.retry_base_delay * (2 ** (attempt - 1)) + random.uniform(0, 1)
        logger.debug("Backing off %0.1fs (attempt %d)", delay, attempt)
        time.sleep(min(delay, 60))

    def _estimate_total_pages(self, html: str) -> int:
        """Estimate total review pages from pagination info (override in adapter)."""
        return 0
