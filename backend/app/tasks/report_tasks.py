"""Scheduled report generation and email delivery tasks."""
import logging
from datetime import datetime, timezone, timedelta
from app.extensions import db
from app.tasks import celery_app
from app.models.product import Product
from app.models.comment import Comment, CommentAnalysis
from app.utils.email import send_report_email
from app.services.scoring_service import score_all_products, get_category_heat
from app.services.analysis_service import get_dashboard_overview, get_trend_data, get_keyword_rank
from app.services.alert_service import run_all_checks as _run_alert_checks

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def send_daily_report(self):
    """Generate and email a daily summary report to all configured recipients."""
    from flask import current_app
    recipients = current_app.config.get("REPORT_RECIPIENTS", "")
    if not recipients:
        logger.info("No report recipients configured, skipping daily report")
        return {"status": "skipped", "reason": "no recipients"}

    html = _build_daily_report_html()
    to_list = [r.strip() for r in recipients.split(",") if r.strip()]
    results = []
    for to in to_list:
        ok = send_report_email(to, f"每日报告 - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}", html)
        results.append({"to": to, "sent": ok})
    return {"status": "done", "recipients": results}


@celery_app.task(bind=True, max_retries=3)
def send_weekly_report(self):
    """Generate and email a weekly summary report."""
    from flask import current_app
    recipients = current_app.config.get("REPORT_RECIPIENTS", "")
    if not recipients:
        logger.info("No report recipients configured, skipping weekly report")
        return {"status": "skipped", "reason": "no recipients"}

    html = _build_weekly_report_html()
    to_list = [r.strip() for r in recipients.split(",") if r.strip()]
    results = []
    for to in to_list:
        ok = send_report_email(to, f"周报 - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}", html)
        results.append({"to": to, "sent": ok})
    return {"status": "done", "recipients": results}


def _build_daily_report_html():
    """Build HTML for daily report."""
    overview = get_dashboard_overview()
    scored = score_all_products()[:5]
    categories = get_category_heat(days=7)

    html_parts = []

    # Overview section
    html_parts.append(f"""<h3 style="color:#409eff;">数据概览</h3>
<table style="width:100%; border-collapse:collapse;">
<tr><td style="padding:8px; border:1px solid #eee;">总评论数</td><td style="padding:8px; border:1px solid #eee; font-weight:bold;">{overview['total_comments']}</td></tr>
<tr><td style="padding:8px; border:1px solid #eee;">已分析评论</td><td style="padding:8px; border:1px solid #eee; font-weight:bold;">{overview['analyzed_count']}</td></tr>
<tr><td style="padding:8px; border:1px solid #eee;">平均评分</td><td style="padding:8px; border:1px solid #eee; font-weight:bold;">{overview['avg_rating']}</td></tr>
<tr><td style="padding:8px; border:1px solid #eee;">疑似虚假评论</td><td style="padding:8px; border:1px solid #eee; font-weight:bold; color:#f56c6c;">{overview['fake_review_count']}</td></tr>
</table>""")

    # Top scored products
    if scored:
        html_parts.append('<h3 style="color:#409eff; margin-top:20px;">评分最高商品</h3>')
        for s in scored[:5]:
            uptrend_tag = '📈' if s.get('uptrend', {}).get('is_uptrend') else ''
            html_parts.append(f"""<div style="padding:8px; border-bottom:1px solid #f0f0f0;">
<div style="font-weight:bold;">{uptrend_tag} {s['product_name']}</div>
<div style="font-size:13px; color:#666;">综合评分: {s['composite_score']} | 情感: {s['dimensions']['sentiment']['score']} | 增长: {s['dimensions']['growth'].get('growth_rate', 'N/A')}%</div>
</div>""")

    # Category heat
    if categories:
        html_parts.append('<h3 style="color:#409eff; margin-top:20px;">品类热度 (7天)</h3>')
        for cat in categories[:5]:
            direction = "上升" if cat.get("comment_growth_rate", 0) > 0 else "下降"
            html_parts.append(f"""<div style="padding:6px; border-bottom:1px solid #f0f0f0;">
<span style="font-weight:bold;">{cat['tag_name']}</span> 热度 {cat['heat_score']} | 评论 {direction} {cat.get('comment_growth_rate', 0):+.1f}% | 好评率 {cat['positive_rate']}%
</div>""")

    return "".join(html_parts)


def _build_weekly_report_html():
    """Build HTML for weekly report (more detailed)."""
    daily_html = _build_daily_report_html()
    trend = get_trend_data(days=30)
    keywords = get_keyword_rank(limit=15)

    extra_parts = []

    # Sentiment trend summary
    if trend:
        pos = sum(d.get("positive", 0) for d in trend)
        neg = sum(d.get("negative", 0) for d in trend)
        neu = sum(d.get("neutral", 0) for d in trend)
        total = pos + neg + neu or 1
        extra_parts.append(f"""<h3 style="color:#409eff; margin-top:20px;">情感趋势 (30天)</h3>
<div>正面: {pos} ({pos/total*100:.1f}%)</div>
<div>负面: {neg} ({neg/total*100:.1f}%)</div>
<div>中性: {neu} ({neu/total*100:.1f}%)</div>""")

    # Top keywords
    if keywords:
        extra_parts.append(f"""<h3 style="color:#409eff; margin-top:20px;">高频关键词</h3>
<div>{'、'.join(k['word'] for k in keywords[:10])}</div>""")

    return daily_html + "".join(extra_parts)


@celery_app.task
def run_alert_checks():
    """Periodic alert check task, runs every 30 minutes."""
    return _run_alert_checks()
