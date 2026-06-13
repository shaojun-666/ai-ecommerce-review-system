"""Crawl Discovery Service — automatic product discovery across platforms.

Discovers hot/trending products from e-commerce category pages without
requiring manual URL input. Integrates with CrawlTask to queue discovered
products for crawling.

Flow:
    1. Fetch category listing pages for each platform
    2. Extract product URLs/titles/prices from listing HTML
    3. Deduplicate against known products (by URL + platform_product_id)
    4. Create CrawlTask records for new discoveries
    5. Optionally trigger crawl immediately
"""
import re
import json
import logging
import time
import random
from typing import Optional
from urllib.parse import urljoin

from app.extensions import db
from app.crawler.anti_bot import AntiBotMiddleware
from app.models.product import Product
from app.models.crawl_task import CrawlTask

logger = logging.getLogger(__name__)

# ── Platform seed categories ──────────────────────────────────────────────
# These are listing/category/search page URLs used to discover products.
# Each entry: {name, platform, url, icon}
SEED_CATEGORIES = [
    # ── JD (京东) ──
    {"name": "手机",       "platform": "jd", "icon": "📱", "url": "https://channel.jd.com/9987-6533.html"},
    {"name": "电脑",       "platform": "jd", "icon": "💻", "url": "https://channel.jd.com/670-671.html"},
    {"name": "耳机",       "platform": "jd", "icon": "🎧", "url": "https://channel.jd.com/9987-6533-6525.html"},
    {"name": "男装",       "platform": "jd", "icon": "👔", "url": "https://channel.jd.com/1315-1342.html"},
    {"name": "女装",       "platform": "jd", "icon": "👗", "url": "https://channel.jd.com/1315-1343.html"},
    {"name": "美妆护肤",   "platform": "jd", "icon": "💄", "url": "https://channel.jd.com/1672-1675.html"},
    {"name": "零食",       "platform": "jd", "icon": "🍪", "url": "https://channel.jd.com/1320-1585.html"},
    {"name": "家居",       "platform": "jd", "icon": "🛋️", "url": "https://channel.jd.com/12118-12120.html"},
    {"name": "运动鞋",     "platform": "jd", "icon": "👟", "url": "https://channel.jd.com/1318-1368.html"},
    {"name": "图书",       "platform": "jd", "icon": "📚", "url": "https://channel.jd.com/1713-3263.html"},
    {"name": "母婴",       "platform": "jd", "icon": "🍼", "url": "https://channel.jd.com/12218-12220.html"},
    {"name": "宠物",       "platform": "jd", "icon": "🐾", "url": "https://channel.jd.com/12218-12222.html"},
    {"name": "汽车用品",   "platform": "jd", "icon": "🚗", "url": "https://channel.jd.com/12218-12224.html"},
    {"name": "家用电器",   "platform": "jd", "icon": "🔌", "url": "https://channel.jd.com/737-738.html"},
    # ── Taobao (淘宝) ──
    {"name": "女装",       "platform": "taobao", "icon": "👗", "url": "https://www.taobao.com/list/item/16-1101.htm"},
    {"name": "男装",       "platform": "taobao", "icon": "👔", "url": "https://www.taobao.com/list/item/16-1102.htm"},
    {"name": "手机",       "platform": "taobao", "icon": "📱", "url": "https://www.taobao.com/list/item/11-50012164.htm"},
    {"name": "美妆",       "platform": "taobao", "icon": "💄", "url": "https://www.taobao.com/list/item/16-1103.htm"},
    {"name": "家居",       "platform": "taobao", "icon": "🛋️", "url": "https://www.taobao.com/list/item/16-50007218.htm"},
    {"name": "运动户外",   "platform": "taobao", "icon": "🏃", "url": "https://www.taobao.com/list/item/16-50013864.htm"},
    {"name": "食品",       "platform": "taobao", "icon": "🍪", "url": "https://www.taobao.com/list/item/16-50002768.htm"},
    {"name": "母婴",       "platform": "taobao", "icon": "🍼", "url": "https://www.taobao.com/list/item/16-50008165.htm"},
    {"name": "家电",       "platform": "taobao", "icon": "🔌", "url": "https://www.taobao.com/list/item/11-50012164.htm"},
    # ── PDD (拼多多) ──
    {"name": "女装",       "platform": "pdd", "icon": "👗", "url": "https://mobile.yangkeduo.com/cate.html?category_id=10929"},
    {"name": "男装",       "platform": "pdd", "icon": "👔", "url": "https://mobile.yangkeduo.com/cate.html?category_id=10930"},
    {"name": "手机数码",   "platform": "pdd", "icon": "📱", "url": "https://mobile.yangkeduo.com/cate.html?category_id=10848"},
    {"name": "美妆",       "platform": "pdd", "icon": "💄", "url": "https://mobile.yangkeduo.com/cate.html?category_id=10937"},
    {"name": "食品",       "platform": "pdd", "icon": "🍪", "url": "https://mobile.yangkeduo.com/cate.html?category_id=10933"},
    {"name": "家居",       "platform": "pdd", "icon": "🛋️", "url": "https://mobile.yangkeduo.com/cate.html?category_id=10940"},
    {"name": "运动",       "platform": "pdd", "icon": "🏃", "url": "https://mobile.yangkeduo.com/cate.html?category_id=10943"},
    {"name": "母婴",       "platform": "pdd", "icon": "🍼", "url": "https://mobile.yangkeduo.com/cate.html?category_id=10949"},
    {"name": "图书",       "platform": "pdd", "icon": "📚", "url": "https://mobile.yangkeduo.com/cate.html?category_id=11011"},
]


class DiscoveredProduct:
    """Result of discovering a product from a listing page."""

    def __init__(self, *, title: str, url: str, platform: str,
                 platform_product_id: str = "", price: float = 0.0,
                 category: str = ""):
        self.title = title
        self.url = url
        self.platform = platform
        self.platform_product_id = platform_product_id
        self.price = price
        self.category = category

    def __repr__(self):
        return f"<DiscoveredProduct {self.platform}:{self.title[:30]}>"


class DiscoveryStats:
    """Statistics for a discovery run."""

    def __init__(self):
        self.categories_processed = 0
        self.products_found = 0
        self.products_new = 0
        self.products_duplicate = 0
        self.errors = 0
        self.tasks_created = 0

    def to_dict(self):
        return {
            "categories_processed": self.categories_processed,
            "products_found": self.products_found,
            "products_new": self.products_new,
            "products_duplicate": self.products_duplicate,
            "errors": self.errors,
            "tasks_created": self.tasks_created,
        }


class CrawlDiscoveryService:
    """Discover products from e-commerce category/listing pages.

    Uses AntiBotMiddleware for HTTP requests with retry and rate limiting.
    Parses platform-specific listing page HTML to extract product info.
    """

    def __init__(self):
        # One anti-bot instance per platform for session persistence
        self._clients: dict[str, AntiBotMiddleware] = {}

    def _get_client(self, platform: str) -> AntiBotMiddleware:
        if platform not in self._clients:
            delays = {"jd": (2.0, 5.0), "taobao": (3.0, 6.0), "pdd": (3.0, 6.0)}
            min_d, max_d = delays.get(platform, (2.0, 4.0))
            self._clients[platform] = AntiBotMiddleware(min_delay=min_d, max_delay=max_d)
        return self._clients[platform]

    # ── Public API ──────────────────────────────────────────────────────

    def get_available_categories(self) -> list[dict]:
        """Return all seed categories grouped by platform."""
        result = {}
        for cat in SEED_CATEGORIES:
            platform = cat["platform"]
            if platform not in result:
                result[platform] = []
            result[platform].append({
                "name": cat["name"],
                "url": cat["url"],
                "icon": cat.get("icon", "📦"),
            })
        return result

    def discover_from_category(self, category: dict, max_products: int = 20) -> list[DiscoveredProduct]:
        """Discover products from a single category listing page.

        Args:
            category: Dict with {name, platform, url, icon}.
            max_products: Maximum products to extract.

        Returns:
            List of DiscoveredProduct instances.
        """
        url = category["url"]
        platform = category["platform"]
        client = self._get_client(platform)
        category_name = category["name"]

        logger.info("Discovering products from %s [%s]: %s", platform.upper(), category_name, url)

        try:
            resp = client.get(url)
            if resp.status_code != 200:
                logger.warning("Failed to fetch %s: HTTP %d", url, resp.status_code)
                return []

            html = resp.text
            if not html or len(html) < 200:
                logger.warning("Empty/short response from %s", url)
                return []

            products = self._parse_listing_page(html, platform, category_name)
            products = products[:max_products]

            logger.info("Discovered %d products from %s [%s]", len(products), platform.upper(), category_name)
            return products

        except Exception as e:
            logger.error("Error discovering from %s: %s", url, e, exc_info=True)
            return []

    def discover_all_categories(self, platforms: Optional[list[str]] = None,
                                max_per_category: int = 20) -> tuple[list[DiscoveredProduct], DiscoveryStats]:
        """Discover products from ALL seed categories.

        Args:
            platforms: List of platforms to include (None = all).
            max_per_category: Max products per category.

        Returns:
            (all_discovered_products, stats)
        """
        stats = DiscoveryStats()
        all_products = []

        for cat in SEED_CATEGORIES:
            if platforms and cat["platform"] not in platforms:
                continue

            stats.categories_processed += 1
            products = self.discover_from_category(cat, max_products=max_per_category)
            all_products.extend(products)
            stats.products_found += len(products)
            time.sleep(random.uniform(1.0, 3.0))  # be polite between categories

        return all_products, stats

    def discover_and_create_tasks(self, user_id: int,
                                  platforms: Optional[list[str]] = None,
                                  max_per_category: int = 20,
                                  auto_start: bool = True,
                                  page_limit: int = 3) -> DiscoveryStats:
        """Discover products and create CrawlTasks for new ones.

        This is the main entry point for auto-crawl.

        Args:
            user_id: Owner for created crawl tasks.
            platforms: Platforms to crawl (None = all).
            max_per_category: Max products per category.
            auto_start: Whether to immediately launch crawl tasks.
            page_limit: Review pages to crawl per task.

        Returns:
            DiscoveryStats with results.
        """
        products, stats = self.discover_all_categories(platforms, max_per_category)

        for dp in products:
            # Dedup: check if product already known (by URL or platform_product_id)
            if self._is_known_product(dp):
                stats.products_duplicate += 1
                continue

            # Create product record
            product = self._ensure_product(dp, user_id)
            if not product:
                stats.errors += 1
                continue

            stats.products_new += 1

            # Create crawl task
            task = CrawlTask(
                user_id=user_id,
                product_id=product.id,
                name=f"自动: {dp.title[:50]}",
                platform=dp.platform,
                url=dp.url,
                page_limit=page_limit,
                status="pending",
            )
            db.session.add(task)
            db.session.flush()
            stats.tasks_created += 1

            if auto_start:
                self._launch_task(task)

        db.session.commit()

        logger.info(
            "Discovery complete: %d found, %d new, %d dup, %d tasks created",
            stats.products_found, stats.products_new,
            stats.products_duplicate, stats.tasks_created,
        )
        return stats

    # ── Internal helpers ─────────────────────────────────────────────────

    def _parse_listing_page(self, html: str, platform: str,
                            category_name: str) -> list[DiscoveredProduct]:
        """Parse listing page HTML per platform to extract products."""
        if platform == "jd":
            return self._parse_jd_listing(html, category_name)
        elif platform == "taobao":
            return self._parse_taobao_listing(html, category_name)
        elif platform == "pdd":
            return self._parse_pdd_listing(html, category_name)
        return []

    def _parse_jd_listing(self, html: str, category_name: str) -> list[DiscoveredProduct]:
        """Extract products from JD channel/category page."""
        products = []
        # Pattern 1: gl-item divs (standard listing)
        # Look for product URLs in the format: https://item.jd.com/NUMBER.html
        urls = set(re.findall(r'https://item\.jd\.com/(\d+)\.html', html))
        for pid in urls:
            full_url = f"https://item.jd.com/{pid}.html"
            # Extract title from nearby data
            title_match = re.search(
                r'<img[^>]+alt="([^"]*)"[^>]*data-lazy-img[^>]*>[^<]*'
                rf'<a[^>]*href=".*?{re.escape(pid)}[^"]*"',
                html
            )
            title = ""
            if title_match:
                title = title_match.group(1).strip()
            else:
                # Try simpler title extraction near the URL
                title = self._extract_title_near_url(html, pid)

            products.append(DiscoveredProduct(
                title=title or f"JD商品{pid}",
                url=full_url,
                platform="jd",
                platform_product_id=pid,
                category=category_name,
            ))

        return products

    def _parse_taobao_listing(self, html: str, category_name: str) -> list[DiscoveredProduct]:
        """Extract products from Taobao list page."""
        products = []

        # Pattern: data-id or href containing id=XXXXX
        # Taobao item URLs: https://item.taobao.com/item.htm?id=XXXXX
        for match in re.finditer(r'data-id=["\'](\d+)["\']', html):
            item_id = match.group(1)
            url = f"https://item.taobao.com/item.htm?id={item_id}"

            # Try to extract title nearby
            title = self._extract_title_near_match(html, match.start(), 'data-title')
            products.append(DiscoveredProduct(
                title=title or f"淘宝商品{item_id}",
                url=url,
                platform="taobao",
                platform_product_id=item_id,
                category=category_name,
            ))

        if not products:
            # Fallback: look for item URLs directly
            ids = re.findall(r'id=(\d+)', html)
            seen = set()
            for item_id in ids:
                if item_id not in seen and len(item_id) >= 8:
                    seen.add(item_id)
                    products.append(DiscoveredProduct(
                        title=f"淘宝商品{item_id}",
                        url=f"https://item.taobao.com/item.htm?id={item_id}",
                        platform="taobao",
                        platform_product_id=item_id,
                        category=category_name,
                    ))

        return products

    def _parse_pdd_listing(self, html: str, category_name: str) -> list[DiscoveredProduct]:
        """Extract products from PDD mobile category page."""
        products = []

        # Try JSON embedded in the page first
        # PDD often embeds product data in window.__INITIAL_STATE__
        json_match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', html)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                # Navigate the PDD data structure
                mall_data = data.get("mallData") or data.get("homeData") or data
                for key in ["list", "items", "goodsList", "productList"]:
                    items = mall_data.get(key, [])
                    if items and isinstance(items, list):
                        for item in items:
                            item_id = str(item.get("goods_id") or item.get("productId") or item.get("id", ""))
                            if not item_id:
                                continue
                            title = item.get("goods_name") or item.get("productName") or item.get("name", "")
                            url = f"https://mobile.yangkeduo.com/goods{'' if item_id.startswith('1') else '1'}.html?goods_id={item_id}"
                            products.append(DiscoveredProduct(
                                title=title[:100],
                                url=url,
                                platform="pdd",
                                platform_product_id=item_id,
                                price=float(item.get("price", 0)) / 100 if item.get("price") else 0,
                                category=category_name,
                            ))
                        break
            except (json.JSONDecodeError, AttributeError):
                pass

        if not products:
            # Pattern: /goods.html?goods_id=NUMBER or goods_id=NUMBER
            ids = re.findall(r'goods_id=(\d+)', html)
            seen = set()
            for gid in ids:
                if gid not in seen:
                    seen.add(gid)
                    products.append(DiscoveredProduct(
                        title=f"拼多多商品{gid}",
                        url=f"https://mobile.yangkeduo.com/goods1.html?goods_id={gid}",
                        platform="pdd",
                        platform_product_id=gid,
                        category=category_name,
                    ))

        return products

    @staticmethod
    def _extract_title_near_url(html: str, pid: str) -> str:
        """Extract a product title near a given PID reference in HTML."""
        idx = html.find(pid)
        if idx < 0:
            return ""
        # Look backwards for title-like attributes
        before = html[max(0, idx - 500):idx]
        for attr in ['title="', 'alt="']:
            m = re.search(rf'{re.escape(attr)}([^"]*)"', before)
            if m and len(m.group(1)) > 3:
                return m.group(1).strip()
        return ""

    @staticmethod
    def _extract_title_near_match(html: str, pos: int, attr: str) -> str:
        """Extract an attribute value near a given position."""
        # Look backwards for the attribute
        before = html[max(0, pos - 300):pos]
        m = re.search(rf'{re.escape(attr)}=["\']([^"\']*)["\']', before)
        if m:
            return m.group(1).strip()[:100]
        return ""

    @staticmethod
    def _is_known_product(dp: DiscoveredProduct) -> bool:
        """Check if a product already exists (by URL or platform_product_id)."""
        if not dp.url and not dp.platform_product_id:
            return False

        query = Product.query
        conditions = []
        if dp.url:
            conditions.append(Product.url == dp.url)
        if dp.platform_product_id:
            conditions.append(
                db.and_(
                    Product.platform == dp.platform,
                    Product.platform_product_id == dp.platform_product_id,
                )
            )
        if conditions:
            from sqlalchemy import or_
            return query.filter(or_(*conditions)).first() is not None
        return False

    @staticmethod
    def _ensure_product(dp: DiscoveredProduct, user_id: int):
        """Create a product record for a discovered product."""
        product = Product(
            name=dp.title[:255] or f"{dp.platform}产品_{int(time.time())}",
            platform=dp.platform,
            platform_product_id=dp.platform_product_id or "",
            url=dp.url,
            user_id=user_id,
        )
        db.session.add(product)
        db.session.flush()
        return product

    @staticmethod
    def _launch_task(task: CrawlTask):
        """Dispatch a crawl task via Celery."""
        try:
            from app.tasks.crawl_tasks import run_crawl
            run_crawl.delay(task.id)
            task.status = "pending"
            logger.info("Auto-launched crawl task %d: %s", task.id, task.name)
        except Exception as e:
            logger.warning("Failed to auto-launch task %d: %s", task.id, e)
