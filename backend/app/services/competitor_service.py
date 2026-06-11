"""Competitor auto-discovery service.
Finds similar products by shared tags, keywords, and platform."""
import logging
from collections import defaultdict
from app.extensions import db
from app.models.product import Product

logger = logging.getLogger(__name__)


def discover_competitors(product_id=None, min_tag_overlap=1):
    """Discover competitor products.

    If product_id is given, find competitors for that specific product.
    Otherwise, discover all competitor groupings across all products.
    """
    if product_id:
        return _find_competitors_for_product(product_id, min_tag_overlap)
    return _discover_all_competitor_groups(min_tag_overlap)


def _find_competitors_for_product(product_id, min_tag_overlap=1):
    """Find competitors for a specific product based on shared tags."""
    product = db.session.get(Product, product_id)
    if not product:
        return None

    tag_ids = [t.id for t in product.tags]
    if not tag_ids:
        return {"product": product.to_dict(), "competitors": []}

    # Find other products sharing at least N tags
    competitors = []
    for other in Product.query.filter(Product.id != product_id).all():
        shared = [t for t in other.tags if t.id in tag_ids]
        if len(shared) >= min_tag_overlap:
            score = _compute_competitor_score(product, other, tag_ids)
            competitors.append({
                "product": other.to_dict(),
                "shared_tags": [t.name for t in shared],
                "competitor_score": score,
                "same_platform": product.platform == other.platform and bool(product.platform),
            })

    competitors.sort(key=lambda x: x["competitor_score"], reverse=True)
    return {"product": product.to_dict(), "competitors": competitors[:20]}


def _discover_all_competitor_groups(min_tag_overlap=1):
    """Group all products into competitor clusters by shared tags."""
    tag_to_products = defaultdict(list)
    for p in Product.query.all():
        for t in p.tags:
            tag_to_products[t.id].append(p)

    seen_pairs = set()
    groups = []
    for p in Product.query.all():
        tag_ids = [t.id for t in p.tags]
        for other in Product.query.filter(Product.id != p.id).all():
            pair_key = tuple(sorted([p.id, other.id]))
            if pair_key in seen_pairs:
                continue
            shared = [t for t in other.tags if t.id in tag_ids]
            if len(shared) >= min_tag_overlap:
                seen_pairs.add(pair_key)
                score = _compute_competitor_score(p, other, tag_ids)
                groups.append({
                    "product_a": {"id": p.id, "name": p.name, "platform": p.platform},
                    "product_b": {"id": other.id, "name": other.name, "platform": other.platform},
                    "shared_tags": [t.name for t in shared],
                    "competitor_score": score,
                    "same_platform": p.platform == other.platform and bool(p.platform),
                })

    groups.sort(key=lambda x: x["competitor_score"], reverse=True)
    return groups[:50]


def _compute_competitor_score(product_a, product_b, tag_ids):
    """Compute a competitor similarity score (0-100)."""
    score = 0

    # Tag overlap (0-40 points)
    shared_tags = [t for t in product_b.tags if t.id in tag_ids]
    total_tags = max(len(tag_ids), len(product_b.tags))
    if total_tags > 0:
        score += (len(shared_tags) / total_tags) * 40

    # Same platform (0-20 points)
    if product_a.platform and product_b.platform and product_a.platform == product_b.platform:
        score += 20

    # Name keyword overlap (0-30 points)
    words_a = set(product_a.name.lower().split())
    words_b = set(product_b.name.lower().split())
    if words_a and words_b:
        overlap = len(words_a & words_b)
        total = len(words_a | words_b)
        if total > 0:
            score += (overlap / total) * 30

    # Same platform_product_id prefix (0-10 points)
    if product_a.platform_product_id and product_b.platform_product_id:
        prefix_a = product_a.platform_product_id.split("_")[0]
        prefix_b = product_b.platform_product_id.split("_")[0]
        if prefix_a == prefix_b:
            score += 10

    return round(min(score, 100), 1)


def get_competitor_summary():
    """Return a summary of competitor landscape across all categories."""
    groups = _discover_all_competitor_groups()
    return {
        "total_pairs": len(groups),
        "high_overlap": sum(1 for g in groups if g["competitor_score"] >= 60),
        "same_platform_count": sum(1 for g in groups if g["same_platform"]),
        "top_pairs": groups[:20],
    }
