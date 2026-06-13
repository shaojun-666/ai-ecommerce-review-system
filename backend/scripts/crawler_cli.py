#!/usr/bin/env python3
"""Interactive crawler CLI — standalone TUI for e-commerce data acquisition.

Usage:
    # Interactive menu
    python scripts/crawler_cli.py

    # One-shot: crawl a single product URL
    python scripts/crawler_cli.py crawl --platform jd --url "https://item.jd.com/10000000.html" --pages 5

    # Batch: crawl URLs from a file (one URL per line)
    python scripts/crawler_cli.py batch --file urls.txt --pages 3

    # Stats: show crawl statistics
    python scripts/crawler_cli.py stats

    # Search: crawl products by keyword across a platform
    python scripts/crawler_cli.py search --platform jd --keyword "手机" --pages 2
"""
import argparse
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Optional

# Ensure the backend directory is on sys.path so we can import app modules
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("APP_CONFIG", "development")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("crawler_cli")


# ---------------------------------------------------------------------------
# Lazy app initialisation (so help / stats don't require a live DB)
# ---------------------------------------------------------------------------
_app = None


def _get_app():
    global _app
    if _app is None:
        from app import create_app
        _app = create_app(os.getenv("APP_CONFIG", "development"))
        _app.app_context().push()
    return _app


def _get_db():
    from app.extensions import db
    return db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _now():
    return datetime.now(timezone.utc)


def _format_duration(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h{m:02d}m{s:02d}s"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def _print_header(title: str):
    width = 60
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


# ---------------------------------------------------------------------------
# Crawler factory
# ---------------------------------------------------------------------------
def _get_crawler(platform: str):
    """Return a crawler instance for *platform* (jd / taobao / pdd)."""
    platform = platform.strip().lower()
    if platform == "jd":
        from app.crawler.adapters.jd import JDCrawler
        return JDCrawler()
    elif platform == "taobao":
        from app.crawler.adapters.taobao import TaobaoCrawler
        return TaobaoCrawler()
    elif platform == "pdd":
        from app.crawler.adapters.pdd import PDDCrawler
        return PDDCrawler()
    else:
        raise ValueError(f"Unsupported platform: {platform!r} (use jd / taobao / pdd)")


# ---------------------------------------------------------------------------
# Core crawl logic
# ---------------------------------------------------------------------------
def _upsert_product(app, platform: str, product_data: dict, url: str) -> Optional[int]:
    """Insert or update a product record. Returns product id."""
    db = _get_db()
    from app.models.product import Product

    platform_product_id = product_data.get("platform_product_id", "") or product_data.get("id", "")
    name = (product_data.get("name") or product_data.get("title") or "Unknown Product")[:255]
    image_url = product_data.get("image_url") or product_data.get("image") or ""

    # Try to find existing product by platform_product_id
    product = None
    if platform_product_id:
        product = Product.query.filter_by(
            platform=platform, platform_product_id=str(platform_product_id)
        ).first()

    if product is None:
        # Also try matching by URL
        product = Product.query.filter_by(url=url).first()

    if product:
        # Update existing
        product.name = name
        product.image_url = image_url or product.image_url
        product.updated_at = _now()
        db.session.commit()
        logger.info("Updated product: %s (id=%d)", name, product.id)
        return product.id
    else:
        # Create new
        product = Product(
            name=name,
            platform=platform,
            platform_product_id=str(platform_product_id) if platform_product_id else "",
            url=url,
            image_url=image_url,
        )
        db.session.add(product)
        db.session.commit()
        logger.info("Created product: %s (id=%d)", name, product.id)
        return product.id


def _import_reviews(app, product_id: int, reviews: list[dict]) -> dict:
    """Import reviews through the data pipeline. Returns stats dict."""
    db = _get_db()
    from app.services.data_pipeline import DataPipeline

    result, processed = DataPipeline.process_batch(reviews, product_id, session=db.session)

    # Bulk insert processed reviews
    from app.models.comment import Comment
    new_count = 0
    for pr in processed:
        comment = Comment(
            product_id=product_id,
            content=pr.content,
            content_hash=pr.content_hash,
            rating=pr.rating,
            author_name=pr.author_name,
            platform=pr.platform or "",
            source="crawl",
            purchase_time=pr.purchase_time,
        )
        db.session.add(comment)
        new_count += 1

    db.session.commit()

    return {
        "total": result.total,
        "new": new_count,
        "skipped_dup": result.skipped_dup,
        "filtered": result.filtered,
    }


def crawl_product_url(platform: str, url: str, page_limit: int = 5, verbose: bool = True) -> dict:
    """Crawl a single product URL and persist results.

    Returns a summary dict.
    """
    app = _get_app()
    crawler = _get_crawler(platform)
    summary = {"url": url, "platform": platform, "status": "ok", "product_id": None}

    if verbose:
        print(f"  Crawling: {url}")
        print(f"  Platform: {platform.upper()},  Pages: {page_limit}")
        sys.stdout.flush()

    result = crawler.crawl_all(url, page_limit=page_limit)

    if result.error and not result.product:
        summary["status"] = "error"
        summary["error"] = result.error
        if verbose:
            print(f"  ❌ Error: {result.error}")
        return summary

    if result.product:
        if verbose:
            print(f"  Product: {result.product.get('name', result.product.get('title', 'N/A'))}")
        product_id = _upsert_product(app, platform, result.product, url)
        summary["product_id"] = product_id

        if result.reviews:
            stats = _import_reviews(app, product_id, result.reviews)
            summary["reviews"] = stats
            if verbose:
                print(f"  Reviews: {stats['new']} new / {stats['skipped_dup']} dup / {stats['filtered']} filtered")
        else:
            summary["reviews"] = {"new": 0, "total": 0}
            if verbose:
                print(f"  Reviews: none found")

        # Mark product as crawled
        from app.services.data_pipeline import DataPipeline
        DataPipeline.mark_crawled(product_id)

        if result.blocked:
            summary["status"] = "blocked"
            summary["error"] = result.error
            if verbose:
                print(f"  ⚠️  Blocked: {result.error}")
    else:
        summary["status"] = "error"
        summary["error"] = result.error or "No product data extracted"

    return summary


# ---------------------------------------------------------------------------
# Interactive menu
# ---------------------------------------------------------------------------
def _cmd_interactive():
    """Run the interactive TUI menu."""
    _print_header("AI E-Commerce Crawler Console — Interactive Mode")

    while True:
        print()
        print("  [1] Crawl single product URL")
        print("  [2] Batch crawl URLs from file")
        print("  [3] Search product by keyword")
        print("  [4] Show crawl statistics")
        print("  [5] Exit")
        print()

        choice = input("  Select [1-5]: ").strip()

        if choice == "1":
            _interactive_single()
        elif choice == "2":
            _interactive_batch()
        elif choice == "3":
            _interactive_search()
        elif choice == "4":
            _cmd_stats()
        elif choice == "5":
            print("  Bye!")
            break
        else:
            print("  Invalid choice.")


def _select_platform() -> str:
    """Prompt user to select a platform."""
    while True:
        p = input("  Platform [jd/taobao/pdd] (default: jd): ").strip().lower() or "jd"
        if p in ("jd", "taobao", "pdd"):
            return p
        print("  Invalid platform. Choose jd, taobao, or pdd.")


def _interactive_single():
    """Interactive: crawl a single URL."""
    print()
    platform = _select_platform()
    url = input("  Product URL: ").strip()
    if not url:
        print("  No URL provided.")
        return
    pages_str = input("  Max pages [5]: ").strip()
    pages = int(pages_str) if pages_str.isdigit() else 5

    print()
    t0 = time.time()
    summary = crawl_product_url(platform, url, page_limit=pages)
    elapsed = time.time() - t0
    print(f"  Done in {_format_duration(elapsed)}.")


def _interactive_batch():
    """Interactive: batch crawl from a file."""
    print()
    filepath = input("  Path to URL file (one URL per line): ").strip()
    if not filepath or not os.path.isfile(filepath):
        print(f"  File not found: {filepath}")
        return

    with open(filepath, encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]

    if not urls:
        print("  No URLs found in file.")
        return

    platform = _select_platform()
    pages_str = input(f"  Max pages per product [5]: ").strip()
    pages = int(pages_str) if pages_str.isdigit() else 5
    delay_str = input(f"  Delay between products (seconds) [3]: ").strip()
    delay = float(delay_str) if delay_str.replace(".", "").isdigit() else 3.0

    print(f"\n  Queue: {len(urls)} URLs")
    print(f"  Platform: {platform.upper()},  Pages: {pages},  Delay: {delay}s")
    print()

    results = {"ok": 0, "error": 0, "blocked": 0, "total_reviews": 0}
    t0 = time.time()

    for i, url in enumerate(urls, 1):
        print(f"  [{i}/{len(urls)}] ", end="")
        sys.stdout.flush()
        summary = crawl_product_url(platform, url, page_limit=pages, verbose=True)
        if summary["status"] == "ok":
            results["ok"] += 1
        elif summary["status"] == "blocked":
            results["blocked"] += 1
        else:
            results["error"] += 1
        rev = summary.get("reviews", {}) or {}
        results["total_reviews"] += rev.get("new", 0)

        if i < len(urls):
            print(f"  Waiting {delay}s...")
            time.sleep(delay)

    elapsed = time.time() - t0
    print()
    print(f"  Batch complete in {_format_duration(elapsed)}")
    print(f"  OK: {results['ok']},  Errors: {results['error']},  Blocked: {results['blocked']}")
    print(f"  Total new reviews: {results['total_reviews']}")


def _interactive_search():
    """Interactive: search products by keyword."""
    print()
    platform = _select_platform()
    keyword = input("  Search keyword: ").strip()
    if not keyword:
        print("  No keyword provided.")
        return
    pages_str = input("  Search pages [2]: ").strip()
    pages = int(pages_str) if pages_str.isdigit() else 2

    print(f"\n  Searching {platform.upper()} for '{keyword}'...")

    app = _get_app()
    crawler = _get_crawler(platform)

    # Use the crawler's search method if available
    if not hasattr(crawler, "search"):
        print(f"  Search not supported for {platform} yet.")
        return

    t0 = time.time()
    try:
        results = crawler.search(keyword, page_limit=pages)
    except Exception as e:
        logger.error("Search failed: %s", e)
        print(f"  ❌ Search failed: {e}")
        return

    elapsed = time.time() - t0

    products = results if isinstance(results, list) else []
    print(f"\n  Found {len(products)} products in {_format_duration(elapsed)}")

    if not products:
        return

    print()
    for i, p in enumerate(products, 1):
        name = p.get("name", p.get("title", "N/A"))
        price = p.get("price", "?")
        url = p.get("url", "?")
        print(f"  [{i}] {name}  ¥{price}")
        print(f"       {url}")

    print()
    choice = input("  Crawl a product by number (or press Enter to skip all): ").strip()
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(products):
            url = products[idx].get("url", "")
            if url:
                pages_crawl = input("  Max review pages [5]: ").strip()
                crawl_pages = int(pages_crawl) if pages_crawl.isdigit() else 5
                print()
                crawl_product_url(platform, url, page_limit=crawl_pages)
    elif choice.lower() in ("a", "all"):
        pages_crawl = input("  Max review pages per product [3]: ").strip()
        crawl_pages = int(pages_crawl) if pages_crawl.isdigit() else 3
        delay = 5.0
        for i, p in enumerate(products, 1):
            url = p.get("url", "")
            if not url:
                continue
            print(f"\n  [{i}/{len(products)}] Crawling: {p.get('name', url)}")
            crawl_product_url(platform, url, page_limit=crawl_pages, verbose=True)
            if i < len(products):
                print(f"  Waiting {delay}s...")
                time.sleep(delay)


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------
def _cmd_stats():
    """Show crawl statistics from the database."""
    app = _get_app()
    db = _get_db()

    from app.models.product import Product
    from app.models.comment import Comment
    from app.models.crawl_task import CrawlTask

    total_products = Product.query.count()
    total_comments = Comment.query.count()
    total_crawl_tasks = CrawlTask.query.count()
    completed_tasks = CrawlTask.query.filter(CrawlTask.status == "completed").count()
    failed_tasks = CrawlTask.query.filter(CrawlTask.status == "failed").count()

    # Per-platform breakdown
    platforms = db.session.query(Product.platform, db.func.count(Product.id)).group_by(Product.platform).all()

    # Comments per platform
    from sqlalchemy import text
    comments_per_platform = db.session.execute(
        text("""
            SELECT p.platform, COUNT(c.id) as cnt
            FROM products p
            JOIN comments c ON c.product_id = p.id
            GROUP BY p.platform
            ORDER BY cnt DESC
        """)
    ).fetchall()

    # Recent crawl activity
    recent_tasks = CrawlTask.query.order_by(CrawlTask.created_at.desc()).limit(5).all()

    _print_header("Crawl Statistics")
    print(f"  Products:          {total_products}")
    print(f"  Comments:          {total_comments}")
    print(f"  Crawl Tasks:       {total_crawl_tasks} ({completed_tasks} completed, {failed_tasks} failed)")
    print()
    print("  ── Per Platform ──")
    for plat, cnt in platforms:
        print(f"    {plat.upper():8s}  {cnt} products")

    if comments_per_platform:
        print()
        print("  ── Comments per Platform ──")
        for plat, cnt in comments_per_platform:
            print(f"    {plat.upper():8s}  {cnt} comments")

    if recent_tasks:
        print()
        print("  ── Recent Crawl Tasks ──")
        for t in recent_tasks:
            status_icon = {"completed": "✅", "failed": "❌", "crawling": "🔄", "pending": "⏳"}
            icon = status_icon.get(t.status, "❓")
            print(f"    {icon} [{t.platform}] {t.name} — {t.status} ({t.items_new} new / {t.items_found} found)")


# ---------------------------------------------------------------------------
# Command-line subcommands
# ---------------------------------------------------------------------------
def _cmd_crawl(args):
    """Crawl a single product URL."""
    result = crawl_product_url(args.platform, args.url, page_limit=args.pages)
    if result["status"] == "error":
        sys.exit(1)


def _cmd_batch(args):
    """Batch crawl URLs from a file."""
    if not os.path.isfile(args.file):
        print(f"File not found: {args.file}")
        sys.exit(1)

    with open(args.file, encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]

    if not urls:
        print("No URLs found in file.")
        return

    results = {"ok": 0, "error": 0, "blocked": 0, "total_reviews": 0}
    t0 = time.time()

    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] ", end="")
        sys.stdout.flush()
        summary = crawl_product_url(args.platform, url, page_limit=args.pages)
        if summary["status"] == "ok":
            results["ok"] += 1
        elif summary["status"] == "blocked":
            results["blocked"] += 1
        else:
            results["error"] += 1
        rev = summary.get("reviews", {}) or {}
        results["total_reviews"] += rev.get("new", 0)

        if i < len(urls):
            delay = args.delay or 3.0
            time.sleep(delay)

    elapsed = time.time() - t0
    print()
    print(f"Batch complete in {_format_duration(elapsed)}")
    print(f"OK: {results['ok']},  Errors: {results['error']},  Blocked: {results['blocked']}")
    print(f"Total new reviews: {results['total_reviews']}")


def _cmd_search(args):
    """Search and crawl products by keyword."""
    app = _get_app()
    crawler = _get_crawler(args.platform)

    if not hasattr(crawler, "search"):
        print(f"Search not supported for {args.platform} yet.")
        sys.exit(1)

    t0 = time.time()
    try:
        results = crawler.search(args.keyword, page_limit=args.pages)
    except Exception as e:
        logger.error("Search failed: %s", e)
        print(f"Search failed: {e}")
        sys.exit(1)

    elapsed = time.time() - t0
    products = results if isinstance(results, list) else []
    print(f"Found {len(products)} products in {_format_duration(elapsed)}")

    for p in products:
        name = p.get("name", p.get("title", "N/A"))
        price = p.get("price", "?")
        url = p.get("url", "")
        print(f"  {name}  ¥{price}  {url}")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="AI E-Commerce Crawler Console — crawl products and reviews",
    )
    subparsers = parser.add_subparsers(dest="command")

    # crawl
    p_crawl = subparsers.add_parser("crawl", help="Crawl a single product URL")
    p_crawl.add_argument("--platform", "-p", required=True, choices=["jd", "taobao", "pdd"])
    p_crawl.add_argument("--url", "-u", required=True)
    p_crawl.add_argument("--pages", "-n", type=int, default=5)

    # batch
    p_batch = subparsers.add_parser("batch", help="Batch crawl URLs from a file")
    p_batch.add_argument("--file", "-f", required=True)
    p_batch.add_argument("--platform", "-p", required=True, choices=["jd", "taobao", "pdd"])
    p_batch.add_argument("--pages", "-n", type=int, default=5)
    p_batch.add_argument("--delay", "-d", type=float, default=3.0)

    # search
    p_search = subparsers.add_parser("search", help="Search products by keyword")
    p_search.add_argument("--platform", "-p", required=True, choices=["jd", "taobao", "pdd"])
    p_search.add_argument("--keyword", "-k", required=True)
    p_search.add_argument("--pages", "-n", type=int, default=2)

    # stats
    subparsers.add_parser("stats", help="Show crawl statistics")

    args = parser.parse_args()

    if args.command == "crawl":
        _cmd_crawl(args)
    elif args.command == "batch":
        _cmd_batch(args)
    elif args.command == "search":
        _cmd_search(args)
    elif args.command == "stats":
        _cmd_stats()
    else:
        # Default: interactive mode
        _cmd_interactive()


if __name__ == "__main__":
    main()
