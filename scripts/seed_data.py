"""Seed database with rich demo data for interactive experience."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.product import Product
from app.models.comment import Comment, CommentAnalysis
from app.models.analysis_task import AnalysisTask
from app.utils.text_cleaner import content_hash
from datetime import datetime, timezone, timedelta
import random


def seed():
    app = create_app("development")
    with app.app_context():
        db.create_all()

        # Check if already seeded
        if Product.query.first():
            print("Database already seeded, skipping.")
            return

        # ── Users ──
        admin = User(username="admin", email="admin@example.com", role="admin", is_active=True)
        admin.set_password("admin123")
        user1 = User(username="user", email="user@example.com", role="user", is_active=True)
        user1.set_password("user123")
        db.session.add_all([admin, user1])
        db.session.flush()

        # ── Products ──
        products = [
            Product(name="iPhone 15 Pro Max", platform="京东", user_id=admin.id),
            Product(name="华为 Mate 60 Pro", platform="京东", user_id=admin.id),
            Product(name="小米14 Ultra", platform="淘宝", user_id=admin.id),
            Product(name="戴尔 XPS 16", platform="京东", user_id=user1.id),
            Product(name="SONY WH-1000XM5", platform="淘宝", user_id=user1.id),
            Product(name="联想小新 Pro 16", platform="淘宝", user_id=user1.id),
        ]
        db.session.add_all(products)
        db.session.flush()

        now = datetime.now(timezone.utc)

        # ── Helper: build a comment with spread date ──
        def make_comment(product, content, rating, author, days_ago=0, platform=None):
            return Comment(
                product_id=product.id,
                content=content,
                content_hash=content_hash(content),
                rating=rating,
                author_name=author,
                platform=platform or product.platform,
                created_at=now - timedelta(days=days_ago, hours=random.randint(0, 23)),
            )

        # ── Comments (56 total, spread across 30 days) ──
        p = products  # shorthand
        comments = []

        # -- iPhone 15 Pro Max (9 comments) --
        comments.append(make_comment(p[0], "手机性能非常好，A17 Pro芯片太强了，拍照效果也很棒，续航也不错，非常满意！", 5, "数码达人", 0))
        comments.append(make_comment(p[0], "物流很快，第二天就到了，手机包装完好，正品无误", 5, "购物狂人", 1))
        comments.append(make_comment(p[0], "发货太慢了，等了一周才到，客服态度也很差", 1, "暴躁老哥", 2))
        comments.append(make_comment(p[0], "手机还行吧，就是价格有点贵，暂时没发现什么问题", 3, "普通用户", 3))
        comments.append(make_comment(p[0], "原色钛金属太漂亮了，手感很好，就是容易沾指纹", 4, "颜值党", 5))
        comments.append(make_comment(p[0], "电池续航比预期好，刷一天抖音还能剩30%", 5, "重度用户", 7))
        comments.append(make_comment(p[0], "屏幕显示效果一流，ProMotion确实丝滑", 5, "视觉控", 10))
        comments.append(make_comment(p[0], "信号还是老样子，地下车库经常没信号", 2, "通信民工", 14))
        comments.append(make_comment(p[0], "系统流畅度没话说，iOS生态确实好", 4, "果粉", 18))

        # -- 华为 Mate 60 Pro (9 comments) --
        comments.append(make_comment(p[1], "华为拍照真的绝了，卫星通话功能很实用，支持国产！", 5, "花粉用户", 0))
        comments.append(make_comment(p[1], "信号比之前用的手机好太多了，电池耐用，一天一充", 5, "商务精英", 1))
        comments.append(make_comment(p[1], "价格太贵了，性价比不高，而且自带的广告太多了", 2, "理性消费者", 4))
        comments.append(make_comment(p[1], "昆仑玻璃确实耐摔，不小心摔了好几次都没事", 5, "粗心大意", 6))
        comments.append(make_comment(p[1], "系统流畅度不错，但是应用启动速度不如iPhone", 3, "客观评价", 8))
        comments.append(make_comment(p[1], "卫星通话功能太酷了，户外爱好者必备", 5, "户外达人", 11))
        comments.append(make_comment(p[1], "充电速度很快，半小时就能充到80%", 4, "效率控", 15))
        comments.append(make_comment(p[1], "曲面屏贴膜太难了，去了几家店都说贴不好", 3, "贴膜达人", 19))
        comments.append(make_comment(p[1], "鸿蒙生态很强大，和笔记本平板协同工作太方便了", 5, "华为全家桶", 22))

        # -- 小米14 Ultra (9 comments) --
        comments.append(make_comment(p[2], "性价比很高，这个价位能买到这么好的配置很值", 4, "学生党", 2))
        comments.append(make_comment(p[2], "用了三天就出现重启问题，品控有待提高", 1, "倒霉蛋", 3))
        comments.append(make_comment(p[2], "徕卡镜头拍照确实有味道，夜景模式很惊艳", 5, "摄影爱好者", 5))
        comments.append(make_comment(p[2], "miui广告太多了，关都关不完，影响体验", 2, "纯净党", 7))
        comments.append(make_comment(p[2], "骁龙8Gen3性能强劲，打原神全高画质很流畅", 5, "游戏玩家", 9))
        comments.append(make_comment(p[2], "手感很好，白色陶瓷版本颜值很高", 4, "颜控", 12))
        comments.append(make_comment(p[2], "电池不太耐用，一天两充，希望优化续航", 3, "续航焦虑", 16))
        comments.append(make_comment(p[2], "快充速度没话说，120W充电太爽了", 5, "数码控", 20))
        comments.append(make_comment(p[2], "信号一般，电梯里经常没信号", 2, "挑剔用户", 24))

        # -- 戴尔 XPS 16 (9 comments) --
        comments.append(make_comment(p[3], "XPS的屏幕素质一流，做工精致，重量控制得很好", 5, "设计师小王", 1))
        comments.append(make_comment(p[3], "散热不行，轻度使用就发热，这个价位不应该", 2, "技术控", 4))
        comments.append(make_comment(p[3], "轻薄本性能标杆，剪辑4K视频毫无压力", 5, "视频创作者", 6))
        comments.append(make_comment(p[3], "键盘手感不错，回弹适中，适合长时间打字", 4, "文字工作者", 9))
        comments.append(make_comment(p[3], "接口太少，每次都要带拓展坞，很不方便", 2, "外设党", 11))
        comments.append(make_comment(p[3], "屏幕边框很窄，视觉冲击力强，做工一流", 5, "颜值控", 14))
        comments.append(make_comment(p[3], "续航一般般，轻度办公也就6小时左右", 3, "移动办公", 17))
        comments.append(make_comment(p[3], "音质出乎意料的好，看电影很有沉浸感", 4, "影音爱好者", 21))
        comments.append(make_comment(p[3], "windows平台能用Linux子系统，开发很方便", 5, "程序员", 25))

        # -- SONY WH-1000XM5 (10 comments) --
        comments.append(make_comment(p[4], "降噪效果一流，戴上就听不见外界声音了，音质也很棒", 5, "音乐爱好者", 1))
        comments.append(make_comment(p[4], "耳罩有点夹头，戴久了不舒服，而且蓝牙连接偶尔会断", 2, "耳机发烧友", 3))
        comments.append(make_comment(p[4], "索尼大法好，降噪比AirPods Pro强太多了", 5, "索粉", 5))
        comments.append(make_comment(p[4], "佩戴舒适度还行，但夏天有点闷热", 3, "实用派", 8))
        comments.append(make_comment(p[4], "LDAC连接LDAC播放器，音质接近有线耳机了", 5, "HiFi发烧友", 10))
        comments.append(make_comment(p[4], "通话质量一般，风噪环境下对方听不清", 2, "商务人士", 13))
        comments.append(make_comment(p[4], "噪音太大，退货了", 1, "失望用户", 16, "淘宝"))
        comments.append(make_comment(p[4], "电池续航很强，充一次电能用一周", 5, "长期用户", 19))
        comments.append(make_comment(p[4], "外观设计比XM4差远了，折叠收纳也不方便", 3, "老用户", 23))
        comments.append(make_comment(p[4], "多设备连接切换很丝滑，手机和电脑之间无缝切换", 4, "多设备党", 27))

        # -- 联想小新 Pro 16 (10 comments) --
        comments.append(make_comment(p[5], "性价比很高的全能本，16寸大屏很爽", 4, "大学生", 2))
        comments.append(make_comment(p[5], "屏幕素质很棒，2.5K分辨率看文档很清晰", 5, "设计师", 4))
        comments.append(make_comment(p[5], "散热风扇声音有点大，夜深人静的时候很明显", 2, "安静党", 6))
        comments.append(make_comment(p[5], "核显性能足够日常使用，偶尔打打LOL没问题", 4, "轻度游戏", 9))
        comments.append(make_comment(p[5], "做工比想象中好，全金属机身很有质感", 5, "细节控", 12))
        comments.append(make_comment(p[5], "电池续航挺好，办公能用8小时左右", 4, "出差党", 15))
        comments.append(make_comment(p[5], "自带的联想管家太烦人了，各种弹窗广告", 2, "纯净系统", 18))
        comments.append(make_comment(p[5], "接口丰富不用拓展坞，这点比XPS好", 4, "实用主义", 21))
        comments.append(make_comment(p[5], "键盘布局有点怪，方向键半高设计不好用", 3, "键盘控", 25))
        comments.append(make_comment(p[5], "性能释放很激进，稳定35W释放，轻度渲染没问题", 4, "创作者", 28))

        # ── Fake reviews (5, interleaved into comments list above as duplicates) ──
        # Actually add separate fake entries
        fake_reviews = [
            Comment(
                product_id=p[0].id,
                content="好好好好好好好好好好好好好好好好好好",
                content_hash=content_hash("好好好好好好好好好好好好好好好好好好"),
                rating=5,
                author_name="水军001",
                platform="京东",
                created_at=now - timedelta(days=6, hours=random.randint(0, 23)),
            ),
            Comment(
                product_id=p[1].id,
                content="这个产品非常好用，推荐大家购买，非常好非常好非常好",
                rating=5,
                content_hash=content_hash("这个产品非常好用，推荐大家购买，非常好非常好非常好"),
                author_name="水军002",
                platform="京东",
                created_at=now - timedelta(days=13, hours=random.randint(0, 23)),
            ),
            Comment(
                product_id=p[0].id,
                content="物流很快，第二天就到了，手机包装完好，正品无误",
                rating=5,
                content_hash=content_hash("物流很快，第二天就到了，手机包装完好，正品无误"),
                author_name="水军003",
                platform="京东",
                created_at=now - timedelta(days=10, hours=random.randint(0, 23)),
            ),
            Comment(
                product_id=p[2].id,
                content="质量太差了，只值一分钱的东西卖这么贵",
                rating=5,
                content_hash=content_hash("质量太差了，只值一分钱的东西卖这么贵"),
                author_name="矛盾评委",
                platform="淘宝",
                created_at=now - timedelta(days=20, hours=random.randint(0, 23)),
            ),
            Comment(
                product_id=p[3].id,
                content="这是一条非常长的评论，但是内容都是重复的。重复重复重复重复重复重复重复重复重复重复重复重复重复重复重复重复重复重复重复重复重复重复",                rating=5,
                content_hash=content_hash("这是一条非常长的评论，但是内容都是重复的。重复重复重复重复重复重复重复重复重复重复重复重复重复重复重复重复重复重复重复重复重复重复"),
                author_name="灌水用户",
                platform="京东",
                created_at=now - timedelta(days=22, hours=random.randint(0, 23)),
            ),
        ]
        comments.extend(fake_reviews)

        db.session.add_all(comments)
        db.session.flush()

        # ── Analysis Tasks ──
        task1 = AnalysisTask(
            user_id=admin.id,
            name="演示分析任务 (全部评论)",
            status="completed",
            total_count=len(comments) - 8,
            processed_count=len(comments) - 8,
            failed_count=0,
            error_count=0,
            timeout_at=now + timedelta(hours=1),
            completed_at=now - timedelta(hours=1),
            created_at=now - timedelta(hours=3),
        )
        task2 = AnalysisTask(
            user_id=admin.id,
            name="小米14 Ultra 专项分析",
            status="processing",
            total_count=25,
            processed_count=13,
            failed_count=1,
            error_count=1,
            timeout_at=now + timedelta(hours=1),
            created_at=now - timedelta(minutes=30),
        )
        task3 = AnalysisTask(
            user_id=user1.id,
            name="戴尔XPS + 索尼耳机批量分析",
            status="completed_with_errors",
            total_count=19,
            processed_count=17,
            failed_count=2,
            error_count=2,
            timeout_at=now + timedelta(hours=1),
            completed_at=now - timedelta(hours=2),
            created_at=now - timedelta(hours=4),
        )
        db.session.add_all([task1, task2, task3])
        db.session.flush()

        # ── Analysis Results ──
        # UNIQUE(comment_id) constraint means each comment belongs to exactly ONE task.
        # task1: iPhone, 华为, 联想 comments (all analyzed)
        # task2: 小米14 Ultra comments (partial: first 8 of 9 — leave 1 as "in progress")
        # task3: 戴尔XPS + SONY comments (all analyzed)
        # Unanalyzed: last 8 comments from the full list (not touched by any task)

        # Build a set of comment IDs to leave unanalyzed (last 8 comments)
        unanalyzed_ids = {c.id for c in comments[-8:]}
        # Pre-collect comments per product, excluding unanalyzed ones
        def comments_for(product, exclude=None):
            q = Comment.query.filter_by(product_id=product.id).all()
            return [c for c in q if c.id not in (exclude or set())]

        xiaomi_all = comments_for(p[2])
        xps_all = comments_for(p[3])
        sony_all = comments_for(p[4])

        # task1: iPhone (p[0]) + 华为 (p[1]) + 联想 (p[5]) — all their comments except unanalyzed
        task1_products = [p[0], p[1], p[5]]
        task1_comments = []
        for prod in task1_products:
            task1_comments.extend(comments_for(prod, unanalyzed_ids))

        # task2: 小米14 Ultra (p[2]) — first 8 of 9 comments (leave 1 unanalyzed for "processing" feel)
        task2_comments = xiaomi_all[:8]

        # task3: 戴尔XPS (p[3]) + SONY (p[4])
        task3_comments = xps_all + sony_all

        sentiment_config = {
            "positive": {"keywords": ["质量好", "性价比高", "值得推荐", "好用", "满意"], "aspects": {"quality": 0.85, "price": 0.75, "service": 0.8}},
            "negative": {"keywords": ["质量差", "价格贵", "不满意", "服务差"], "aspects": {"quality": 0.3, "price": 0.4, "service": 0.25}},
            "neutral": {"keywords": ["一般", "还行", "中规中矩"], "aspects": {"quality": 0.55, "price": 0.5, "service": 0.5}},
        }

        for c_list, task_id, kw_override in [
            (task1_comments, task1.id, None),
            (task2_comments, task2.id, ["小米", "性价比"]),
            (task3_comments, task3.id, ["高端", "评测"]),
        ]:
            for c in c_list:
                if c.rating >= 4:
                    sentiment = "positive"
                    sentiment_score = round(random.uniform(0.78, 0.98), 2)
                elif c.rating <= 2:
                    sentiment = "negative"
                    sentiment_score = round(random.uniform(0.72, 0.95), 2)
                else:
                    sentiment = "neutral"
                    sentiment_score = round(random.uniform(0.6, 0.8), 2)

                cfg = sentiment_config[sentiment]
                kw = kw_override or cfg["keywords"]

                is_fake = c.author_name in ["水军001", "水军002", "水军003", "矛盾评委", "灌水用户"]
                fake_score = round(random.uniform(0.75, 0.95), 2) if is_fake else round(random.uniform(0.02, 0.25), 2)

                analysis = CommentAnalysis(
                    comment_id=c.id,
                    task_id=task_id,
                    sentiment=sentiment,
                    sentiment_score=sentiment_score,
                    aspects=cfg["aspects"],
                    keywords=kw,
                    summary=f"{'非常满意' if sentiment == 'positive' else '需要改进' if sentiment == 'negative' else '一般'}的商品评价",
                    fake_score=fake_score,
                    model_version="bert-base-chinese-v1.0",
                    analyzed_at=c.created_at + timedelta(minutes=random.randint(5, 60)),
                )
                db.session.add(analysis)

        db.session.commit()
        total_analysis = CommentAnalysis.query.count()
        total_comments = len(comments)
        print(f"Seed complete! Created:")
        print(f"  2 users (admin/admin123, user/user123)")
        print(f"  6 products")
        print(f"  {total_comments} comments (incl. 5 fake reviews)")
        print(f"  {total_analysis} analysis results across 3 tasks")
        print(f"  {total_comments - total_analysis} unanalyzed comments (for 'pending analysis' demo)")
        print(f"\nLogin at http://localhost with admin/admin123")


if __name__ == "__main__":
    seed()
