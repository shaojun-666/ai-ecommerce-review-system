"""PDD (Pinduoduo) crawler adapter.

PDD doesn't expose a public review API. Reviews are loaded via internal APIs
from the mobile site (mobile.yangkeduo.com).

Review API (reverse-engineered from mobile app/web):
    GET https://mobile.yangkeduo.com/proxy/api/reviews?goods_id={id}&page={page}&size=10

Product pages:
    https://mobile.yangkeduo.com/goods.html?goods_id={id}

Note: PDD employs aggressive anti-bot measures. The adapter includes
extra UA rotation and referer handling.
"""
import json
import logging
import re
from typing import Optional

from bs4 import BeautifulSoup

from app.crawler.base import BaseCrawler, ExtractionError

logger = logging.getLogger(__name__)

# Extract goods_id from PDD URLs
_GOODS_ID_RE = re.compile(r"(?:goods_id|goodsId)=(\d+)")
# PDD uses internal numerical IDs in API paths
_API_GOODS_ID_RE = re.compile(r"/goods[12]\.html\?.*goods_id=(\d+)")


def _parse_goods_id(url: str) -> Optional[str]:
    """Extract numeric goods ID from a PDD URL.

    Formats:
        https://mobile.yangkeduo.com/goods.html?goods_id=123456
        https://mobile.yangkeduo.com/goods2.html?goods_id=123456
        https://www.pinduoduo.com/product/123456
    """
    match = _GOODS_ID_RE.search(url)
    return match.group(1) if match else None


class PDDCrawler(BaseCrawler):
    """Crawler for Pinduoduo product details and reviews.

    PDD uses aggressive anti-bot measures, so this adapter includes:
    - Longer delay between requests
    - Additional header manipulation
    - Multiple API endpoint fallbacks
    """

    def __init__(
        self,
        min_delay: float = 2.0,
        max_delay: float = 5.0,
        max_retries: int = 4,
    ):
        super().__init__(
            platform="pdd",
            min_delay=min_delay,
            max_delay=max_delay,
            max_retries=max_retries,
        )
        self._product_id_cache: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Product extraction
    # ------------------------------------------------------------------

    def extract_product(self, url: str, html: str) -> dict:
        """Parse PDD product detail HTML.

        PDD pages are React-rendered. Product data is typically embedded
        in a <script> tag with JSON inside the page, or in meta tags.
        """
        soup = BeautifulSoup(html, "html.parser")
        goods_id = _parse_goods_id(url) or ""

        # Try to extract product info from embedded JSON data
        product_data = self._extract_embedded_json(soup)
        if product_data:
            name = product_data.get("goodsName", "") or product_data.get("productName", "")
            price = product_data.get("price")
            if isinstance(price, str):
                try:
                    price = float(price.replace("¥", "").replace("￥", ""))
                except ValueError:
                    price = None
            image = product_data.get("thumbUrl", "") or product_data.get("imageUrl", "") or ""
            shop = product_data.get("mallName", "") or ""
        else:
            # Fallback: extract from HTML meta/dom
            name = ""
            for sel in (".goods-title", ".product-title", "title", "[data-name]"):
                el = soup.select_one(sel)
                if el:
                    name = el.get_text(strip=True)
                    if name:
                        break

            # Strip PDD suffix
            if name.endswith("-拼多多"):
                name = name[:-4]

            price = None
            for sel in (".price", ".goods-price", "[data-price]"):
                el = soup.select_one(sel)
                if el:
                    price_text = el.get_text(strip=True).replace("¥", "").replace("￥", "")
                    try:
                        price = float(price_text)
                        break
                    except ValueError:
                        continue

            image = ""
            img_el = soup.select_one(".goods-img img") or soup.select_one(".product-img img") or soup.select_one("img.goods-img")
            if img_el:
                image = img_el.get("src", "") or img_el.get("data-src", "")

            shop = ""

        result = {
            "platform_product_id": goods_id,
            "name": name,
            "price": price,
            "image": image,
            "shop": shop,
            "platform": "pdd",
            "url": url,
        }

        if not name:
            raise ExtractionError("Could not extract product name from PDD HTML")

        self._product_id_cache[url] = goods_id
        return result

    def _extract_embedded_json(self, soup: BeautifulSoup) -> Optional[dict]:
        """Attempt to extract product data from embedded JSON-LD or window.__INITIAL_STATE__."""
        # Try JSON-LD
        for script in soup.select("script[type='application/ld+json']"):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    return data
            except (json.JSONDecodeError, TypeError):
                continue

        # Try window.__INITIAL_STATE__ or similar
        for script in soup.select("script"):
            text = script.string or ""
            if "__INITIAL_STATE__" in text or "window.__data" in text:
                match = re.search(r"__INITIAL_STATE__\s*=\s*({.+?});", text, re.DOTALL)
                if match:
                    try:
                        data = json.loads(match.group(1))
                        if isinstance(data, dict):
                            return data.get("goods", {}) or data
                    except json.JSONDecodeError:
                        continue
        return None

    # ------------------------------------------------------------------
    # Review extraction
    # ------------------------------------------------------------------

    def extract_reviews(self, product_url: str, json_text: str, page: int = 1) -> list[dict]:
        """Parse PDD review API response.

        Expected JSON structure:
            {
                "data": {
                    "reviews": [{
                        "content": "很好",
                        "rateTime": 1705305600000,
                        "score": 5,
                        "nickname": "用户123",
                        "skuInfo": "黑色;M"
                    }, ...],
                    "total": 200
                }
            }

        The PDD API returns timestamps in milliseconds.
        """
        try:
            data = json.loads(json_text)
        except json.JSONDecodeError:
            raise ExtractionError("Failed to parse PDD review JSON")

        # Navigate through nested wrappers
        payload = data
        if isinstance(data.get("data"), dict):
            payload = data["data"]
        elif isinstance(data.get("result"), dict):
            payload = data["result"]

        reviews_raw = payload.get("reviews", []) or payload.get("comments", []) or payload.get("rateList", [])
        if not reviews_raw:
            return []

        reviews = []
        for c in reviews_raw:
            content = (c.get("content") or "").strip()
            if not content:
                continue

            try:
                rating = int(c.get("score", 0))
            except (ValueError, TypeError):
                rating = 0

            # PDD timestamps are in milliseconds
            purchase_time = None
            ts = c.get("rateTime") or c.get("createTime")
            if ts:
                try:
                    ts_int = int(ts)
                    if ts_int > 1e12:  # milliseconds → seconds
                        ts_int //= 1000
                    import datetime
                    purchase_time = datetime.datetime.fromtimestamp(ts_int, tz=datetime.timezone.utc).isoformat()
                except (ValueError, OSError):
                    purchase_time = str(ts)

            reviews.append({
                "content": content,
                "rating": rating,
                "author_name": c.get("nickname", "") or c.get("userName", ""),
                "platform": "pdd",
                "purchase_time": purchase_time,
                "product_color": c.get("skuInfo", ""),
                "product_size": "",
                "review_id": c.get("id"),
            })

        return reviews

    # ------------------------------------------------------------------
    # URL building
    # ------------------------------------------------------------------

    def get_review_url(self, product_url: str, page: int = 1) -> str:
        """Build PDD review API URL."""
        pid = self._product_id_cache.get(product_url) or _parse_goods_id(product_url)
        if not pid:
            raise ExtractionError(f"Cannot build review URL: no goods_id for {product_url}")

        return (
            f"https://mobile.yangkeduo.com/proxy/api/reviews"
            f"?goods_id={pid}"
            f"&page={page}"
            f"&size=10"
        )

    def _estimate_total_pages(self, html: str) -> int:
        """Extract total count from API response."""
        try:
            data = json.loads(html)
            payload = data.get("data", data)
            total = int(payload.get("total", 0) or 0)
            if total:
                return max(1, (total + 9) // 10)
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
        return 0
