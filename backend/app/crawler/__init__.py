"""Crawler package for e-commerce data acquisition.

Usage:
    # Direct use in Celery task:
    from app.crawler.adapters.jd import JDCrawler
    crawler = JDCrawler()
    result = crawler.crawl_all("https://item.jd.com/123456.html", page_limit=5)
"""
from app.crawler.base import (
    BaseCrawler,
    CrawlerError,
    CrawlerTimeoutError,
    CrawlerBlockedError,
    EmptyResponseError,
    ExtractionError,
    PageNotFoundError,
    CrawlerResult,
)

__all__ = [
    "BaseCrawler",
    "CrawlerError",
    "CrawlerTimeoutError",
    "CrawlerBlockedError",
    "EmptyResponseError",
    "ExtractionError",
    "PageNotFoundError",
    "CrawlerResult",
]
