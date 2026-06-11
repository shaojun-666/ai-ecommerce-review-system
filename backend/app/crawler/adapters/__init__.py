"""Platform-specific crawler adapters with unified factory.

Available adapters:
    - JDCrawler:      JD.com
    - TaobaoCrawler:  Taobao / Tmall
    - PDDCrawler:     Pinduoduo

Usage:
    from app.crawler.adapters import get_crawler

    # Auto-select by platform
    crawler = get_crawler("taobao")
    result = crawler.crawl_all("https://item.taobao.com/item.htm?id=...")

    # Direct import also works
    from app.crawler.adapters.jd import JDCrawler
"""
from app.crawler.adapters.jd import JDCrawler
from app.crawler.adapters.taobao import TaobaoCrawler
from app.crawler.adapters.pdd import PDDCrawler

# Registry mapping platform names to crawler classes
_CRAWLER_REGISTRY: dict[str, type] = {
    "jd": JDCrawler,
    "taobao": TaobaoCrawler,
    "pdd": PDDCrawler,
}


def get_crawler(platform: str, **kwargs):
    """Factory: get a crawler instance for the given platform.

    Args:
        platform: One of "jd", "taobao", "pdd".
        **kwargs: Passed to the crawler constructor.

    Returns:
        An instance of the appropriate BaseCrawler subclass.

    Raises:
        ValueError: If the platform is not registered.
    """
    cls = _CRAWLER_REGISTRY.get(platform)
    if cls is None:
        raise ValueError(
            f"Unsupported platform: {platform!r}. "
            f"Available: {list(_CRAWLER_REGISTRY)}"
        )
    return cls(**kwargs)


def register_crawler(platform: str, crawler_cls: type):
    """Register a new crawler class for a platform (extensibility hook)."""
    _CRAWLER_REGISTRY[platform] = crawler_cls


__all__ = [
    "JDCrawler",
    "TaobaoCrawler",
    "PDDCrawler",
    "get_crawler",
    "register_crawler",
]
