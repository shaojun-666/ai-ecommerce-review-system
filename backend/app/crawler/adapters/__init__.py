"""Platform-specific crawler adapters.

Available adapters:
    - JDCrawler: JD.com (club.jd.com XHR API + item.jd.com detail page)
"""
from app.crawler.adapters.jd import JDCrawler

__all__ = ["JDCrawler"]
