"""Taobao / Tmall crawler adapter.

Supports both Taobao (item.taobao.com) and Tmall (detail.tmall.com) items.

Review API endpoints:
    Taobao: GET https://rate.taobao.com/feedRateList.htm?auctionNumId={id}&currentPage={page}&pageSize=20
    Tmall:  GET https://rate.tmall.com/list_detail_rate.htm?itemId={id}&currentPage={page}&pageSize=20

Product detail: parsed from item.taobao.com / detail.tmall.com HTML via BeautifulSoup.
"""
import json
import logging
import re
from typing import Optional

from bs4 import BeautifulSoup

from app.crawler.base import BaseCrawler, ExtractionError

logger = logging.getLogger(__name__)

# Extract item ID from Taobao / Tmall URLs
_ITEM_ID_RE = re.compile(r"[?&]id=(\d+)")
# Detect Tmall domain
_TMALL_DOMAIN_RE = re.compile(r"detail\.tmall\.com")


def _parse_item_id(url: str) -> Optional[str]:
    """Extract numeric item ID from a Taobao/Tmall URL.

    Formats:
        https://item.taobao.com/item.htm?id=123456
        https://detail.tmall.com/item.htm?id=123456
    """
    match = _ITEM_ID_RE.search(url)
    return match.group(1) if match else None


def _is_tmall(url: str) -> bool:
    """Check whether the URL is a Tmall item (vs Taobao)."""
    return bool(_TMALL_DOMAIN_RE.search(url))


class TaobaoCrawler(BaseCrawler):
    """Crawler for Taobao / Tmall product details and reviews.

    Handles both platforms transparently by detecting the domain.
    """

    def __init__(
        self,
        min_delay: float = 1.5,
        max_delay: float = 4.0,
        max_retries: int = 3,
    ):
        super().__init__(
            platform="taobao",
            min_delay=min_delay,
            max_delay=max_delay,
            max_retries=max_retries,
        )
        self._product_id_cache: dict[str, str] = {}
        self._is_tmall_cache: dict[str, bool] = {}

    # ------------------------------------------------------------------
    # Product extraction
    # ------------------------------------------------------------------

    def extract_product(self, url: str, html: str) -> dict:
        """Parse Taobao / Tmall product detail page HTML."""
        soup = BeautifulSoup(html, "html.parser")
        item_id = _parse_item_id(url) or ""
        is_tmall = _is_tmall(url)

        # Product name
        name = ""
        for sel in (".tb-title", ".main-title", "title", "#J_Title"):
            el = soup.select_one(sel)
            if el:
                name = el.get_text(strip=True)
                break

        # Strip suffix like "-淘宝网" or "-天猫"
        for suffix in ("-淘宝网", "-天猫", "-Tmall.com"):
            if name.endswith(suffix):
                name = name[:-len(suffix)]
                break

        # Price
        price = None
        for sel in (".tm-price", ".tb-rmb-num", "#J_StrPr49898 > .tb-rmb-num",
                     "#J_Price", "span.price"):
            el = soup.select_one(sel)
            if el:
                price_text = el.get_text(strip=True).replace("¥", "").replace("￥", "")
                try:
                    price = float(price_text)
                    break
                except ValueError:
                    continue

        # Image
        image = ""
        for sel in ("#J_ImgBooth", "#J_Thumb", ".tb-pic img", ".pic img"):
            el = soup.select_one(sel)
            if el:
                image = el.get("src", "") or el.get("data-src", "") or ""
                if image:
                    break

        # Shop name
        shop = ""
        for sel in (".tb-shop-name a", ".shop-name a", ".seller-name a"):
            el = soup.select_one(sel)
            if el:
                shop = el.get_text(strip=True)
                if shop:
                    break

        result = {
            "platform_product_id": item_id,
            "name": name,
            "price": price,
            "image": image,
            "shop": shop,
            "platform": "taobao",
            "url": url,
        }

        if not name:
            raise ExtractionError("Could not extract product name from Taobao HTML")

        self._product_id_cache[url] = item_id
        self._is_tmall_cache[url] = is_tmall
        return result

    # ------------------------------------------------------------------
    # Review extraction
    # ------------------------------------------------------------------

    def extract_reviews(self, product_url: str, json_text: str, page: int = 1) -> list[dict]:
        """Parse Taobao / Tmall review JSON response.

        Taobao format (feedRateList):
            { "comments": [{ "rateContent": "...", "rateDate": "...", "rateScore": 5, ... }], "totalCount": ... }

        Tmall format (list_detail_rate):
            { "rateDetail": { "rateList": [{ ... }], "rateCount": ... } }
        """
        try:
            data = json.loads(json_text)
        except json.JSONDecodeError:
            raise ExtractionError("Failed to parse Taobao review JSON")

        # Try Tmall format first, then Taobao format
        rate_list = []
        source = None

        if "rateDetail" in data:
            rate_list = data["rateDetail"].get("rateList", [])
            source = "tmall"
        elif "comments" in data:
            rate_list = data["comments"]
            source = "taobao"
        elif "rateList" in data:
            rate_list = data["rateList"]
            source = "taobao"

        if not rate_list:
            return []

        reviews = []
        for c in rate_list:
            content = (c.get("rateContent") or "").strip()
            if not content:
                continue

            try:
                rating = int(c.get("rateScore", 0))
            except (ValueError, TypeError):
                rating = 0

            author = ""
            user_info = c.get("displayUserInfo") or c.get("userInfo", {})
            if isinstance(user_info, dict):
                author = user_info.get("displayUserNick", "")
            if not author:
                author = c.get("displayUserNick", "") or c.get("nickname", "")

            reviews.append({
                "content": content,
                "rating": rating,
                "author_name": author,
                "platform": "taobao",
                "purchase_time": c.get("rateDate"),
                "product_color": c.get("auctionSku", ""),
                "product_size": "",
                "review_id": c.get("id"),
            })

        return reviews

    # ------------------------------------------------------------------
    # URL building
    # ------------------------------------------------------------------

    def get_review_url(self, product_url: str, page: int = 1) -> str:
        """Build review API URL for Taobao or Tmall."""
        pid = self._product_id_cache.get(product_url) or _parse_item_id(product_url)
        if not pid:
            raise ExtractionError(f"Cannot build review URL: no item ID for {product_url}")

        is_tmall = self._is_tmall_cache.get(product_url, _is_tmall(product_url))

        if is_tmall:
            return (
                f"https://rate.tmall.com/list_detail_rate.htm"
                f"?itemId={pid}"
                f"&currentPage={page}"
                f"&pageSize=20"
                f"&order=1"
            )
        else:
            return (
                f"https://rate.taobao.com/feedRateList.htm"
                f"?auctionNumId={pid}"
                f"&currentPage={page}"
                f"&pageSize=20"
                f"&order=1"
            )

    def _get_review_source(self, product_url: str) -> str:
        """Determine whether to use Tmall or Taobao API."""
        is_tmall = self._is_tmall_cache.get(product_url, _is_tmall(product_url))
        return "tmall" if is_tmall else "taobao"

    def _estimate_total_pages(self, html: str) -> int:
        """Extract total page count from JSON meta fields."""
        try:
            data = json.loads(html)
            if "rateDetail" in data:
                total = data["rateDetail"].get("rateCount", 0) or 0
            else:
                total = data.get("totalCount", 0) or 0
            if total:
                return max(1, (int(total) + 19) // 20)
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
        return 0
