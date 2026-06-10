"""JD.com crawler adapter.

JD.com reviews are loaded via XHR from club.jd.com, not embedded in the HTML.
Product details are on item.jd.com pages.

Review API format:
    GET https://club.jd.com/comment/productPageComments.action
        ?callback=fetchJSON_comment98vv123
        &productId={id}
        &score=0
        &sortType=5
        &page={page}
        &pageSize=10
        &isShadowSku=0
        &fold=1

    Response: JSONP containing comments array, productCommentSummary, etc.

Product detail extraction:
    HTML from item.jd.com, parsed with BeautifulSoup.
"""
import json
import logging
import re
from typing import Optional

from bs4 import BeautifulSoup

from app.crawler.base import BaseCrawler, ExtractionError

logger = logging.getLogger(__name__)

# Regex to extract product ID from JD.com item URLs
_PRODUCT_ID_RE = re.compile(r"item\.jd\.com[\/:](\d+)")
# JSONP callback pattern
_JSONP_CALLBACK_RE = re.compile(r"fetchJSON_comment98vv\d+")
# JSONP wrapper: remove callback( ... )
_JSONP_WRAP_RE = re.compile(r"^\w+\((.+)\)$", re.DOTALL)


def _parse_product_id(url: str) -> Optional[str]:
    """Extract numeric product ID from a JD.com item URL.

    Supports formats:
        https://item.jd.com/123456.html
        https://item.jd.com/123456.html#crumb
        item.jd.com/123456
    """
    match = _PRODUCT_ID_RE.search(url)
    return match.group(1) if match else None


def _clean_jsonp(text: str) -> str:
    """Remove JSONP wrapper, leaving pure JSON.

    Handles: fetchJSON_comment98vv123({...}) → {...}
    """
    # Remove callback wrapper
    match = _JSONP_WRAP_RE.search(text)
    if match:
        return match.group(1)
    return text


class JDCrawler(BaseCrawler):
    """Crawler for JD.com product details and reviews.

    Uses:
        - item.jd.com HTML for product details (name, price)
        - club.jd.com JSONP API for review pages

    Args:
        min_delay: Minimum seconds between requests (default: 1.0).
        max_delay: Maximum seconds between requests (default: 3.0).
        max_retries: Max retry attempts per request (default: 3).
    """

    def __init__(
        self,
        min_delay: float = 1.0,
        max_delay: float = 3.0,
        max_retries: int = 3,
    ):
        super().__init__(
            platform="jd",
            min_delay=min_delay,
            max_delay=max_delay,
            max_retries=max_retries,
        )
        self._product_id_cache: dict[str, str] = {}

    def extract_product(self, url: str, html: str) -> dict:
        """Parse JD.com product detail page HTML.

        Expected HTML structure (may change — see CI drift detection):
            - <div class="sku-name"> for product name
            - <span class="price" id="jd-price"> for price
        """
        soup = BeautifulSoup(html, "html.parser")
        product_id = _parse_product_id(url)

        # Product name
        name = ""
        name_el = (
            soup.select_one(".sku-name")
            or soup.select_one(".itemInfo-wrap .sku-name")
            or soup.select_one("title")
        )
        if name_el:
            name = name_el.get_text(strip=True)
        # Clean JD suffix from title
        if name.endswith("【京东】"):
            name = name[:-5]

        # Price
        price = None
        price_el = (
            soup.select_one(".p-price")
            or soup.select_one("#jd-price")
            or soup.select_one(".price")
        )
        if price_el:
            price_text = price_el.get_text(strip=True).replace("¥", "").replace("￥", "")
            try:
                price = float(price_text)
            except ValueError:
                pass

        # Image
        image = ""
        img_el = soup.select_one("#spec-img img") or soup.select_one(".pic img")
        if img_el:
            image = img_el.get("src", "") or img_el.get("data-src", "")

        # Shop name
        shop = ""
        shop_el = soup.select_one(".J-hove-wrap .name a") or soup.select_one(".shop-name a")
        if shop_el:
            shop = shop_el.get_text(strip=True)

        result = {
            "platform_product_id": product_id or "",
            "name": name,
            "price": price,
            "image": image,
            "shop": shop,
            "platform": "jd",
            "url": url,
        }

        if not name:
            raise ExtractionError("Could not extract product name from HTML")

        self._product_id_cache[url] = product_id or ""
        return result

    def extract_reviews(self, product_url: str, jsonp_text: str, page: int = 1) -> list[dict]:
        """Parse JD.com review JSONP response.

        The club.jd.com API returns JSONP with this structure:
            {
                "comments": [{
                    "content": "好评",
                    "creationTime": "2024-01-15",
                    "score": 5,
                    "nickname": "用户123",
                    "productColor": "黑色",
                    "productSize": "M"
                }, ...],
                "productCommentSummary": {
                    "commentCountStr": "1.2万+",
                    "averageScore": 4.8
                }
            }
        """
        # Clean JSONP
        try:
            clean = _clean_jsonp(jsonp_text)
            data = json.loads(clean)
        except json.JSONDecodeError:
            # Try to extract JSON from the response directly
            try:
                data = json.loads(jsonp_text)
            except json.JSONDecodeError as e:
                raise ExtractionError(f"Failed to parse JSON response: {e}")

        comments = data.get("comments", [])
        if not comments:
            return []

        reviews = []
        for c in comments:
            content = (c.get("content") or "").strip()
            if not content:
                continue

            try:
                rating = int(c.get("score", 0))
            except (ValueError, TypeError):
                rating = 0

            reviews.append({
                "content": content,
                "rating": rating,
                "author_name": c.get("nickname", ""),
                "platform": "jd",
                "purchase_time": c.get("creationTime"),
                "product_color": c.get("productColor", ""),
                "product_size": c.get("productSize", ""),
                "review_id": c.get("id"),
            })

        return reviews

    def get_review_url(self, product_url: str, page: int = 1) -> str:
        """Build JD.com review API URL for a given product and page."""
        pid = self._product_id_cache.get(product_url) or _parse_product_id(product_url)
        if not pid:
            raise ExtractionError(f"Cannot build review URL: no product ID for {product_url}")

        callback = f"fetchJSON_comment98vv{hash(str(page)) & 0xFFFFFF:06x}"
        return (
            f"https://club.jd.com/comment/productPageComments.action"
            f"?callback={callback}"
            f"&productId={pid}"
            f"&score=0"
            f"&sortType=5"
            f"&page={page}"
            f"&pageSize=10"
            f"&isShadowSku=0"
            f"&fold=1"
        )

    def _estimate_total_pages(self, html: str) -> int:
        """Extract total page count from the JSONP response.

        The response contains productCommentSummary.maxPage or we can
        estimate from commentCount.
        """
        try:
            clean = _clean_jsonp(html)
            data = json.loads(clean)
            summary = data.get("productCommentSummary", {})
            max_page = summary.get("maxPage", 0)
            if max_page:
                return int(max_page)
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
        return 0
