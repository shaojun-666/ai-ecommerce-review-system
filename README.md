# AI E-commerce Review Analysis System

基于 AI 的电商评论智能分析系统，支持多平台评论采集、情感分析、关键词提取、虚假评论检测等功能。

## Project Status

| Module | Tests | Status |
|---|---|---|
| Backend (Flask API + Crawler + Data Pipeline + Cache) | 201/201 passed | ✅ Complete |
| Frontend (Vue 3) | 14/14 passed | ✅ Complete |
| NLP Module | 94/104 passed | ✅ Complete (10 ONNX need network) |
| Docker Deployment | 5/5 containers healthy | ✅ Complete |

## Tech Stack

**Backend**
- Flask + Flask-SQLAlchemy + Flask-Migrate
- PostgreSQL + Redis
- Celery (异步任务队列)
- JWT 认证 + Flask-Limiter 限流
- Pydantic / Marshmallow 数据校验

**Frontend**
- Vue 3 + TypeScript + Vite
- Element Plus UI 组件库
- Pinia 状态管理 + Vue Router
- ECharts 数据可视化

**NLP / AI**
- BERT 中文情感分析模型 (3分类: positive/neutral/negative)
- Qwen2.5-1.5B-Instruct LLM 分析模型
- 关键词提取 (jieba + TF-IDF)
- 虚假评论检测 (启发式规则 + 评分融合)
- 商品属性级情感分析 (aspect-based sentiment)

**DevOps**
- Docker Compose (PostgreSQL, Redis, Backend, Celery, Nginx)
- Gunicorn + Gevent
- Sentry 异常监控

## Quick Start

### Prerequisites

- Docker & Docker Compose (推荐)
- Python 3.10+ (本地开发)
- Node.js 18+ (前端开发)

### 方式一：Docker 一键部署（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/shaojun-666/ai-ecommerce-review-system.git
cd ai-ecommerce-review-system

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，修改 JWT_SECRET_KEY 等敏感信息

# 3. 启动所有服务
docker compose up -d

# 4. 访问
# Frontend: http://localhost
# Backend API: http://localhost:8000/api
# API Docs: http://localhost:8000/api/docs

# 5. 控制
# docker compose stop     # 暂停（保留数据）
# docker compose down     # 停止并删除容器
# docker compose down -v  # 停止并删除容器+数据卷
```

### 方式二：本地开发

```bash
# 1. 启动依赖服务
docker compose up -d postgres redis

# 2. Backend Setup
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
flask db upgrade
python scripts/seed_data.py
gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app

# 3. Frontend Setup (新终端)
cd frontend
npm install
npm run dev

# 4. Celery Worker (可选，异步分析任务)
cd backend
celery -A app.tasks worker -l info

# 5. Access
# Frontend: http://localhost:5173
# Backend API: http://localhost:8000
```

## Demo Experience

Seed the database with demo data and explore the system's features:

```bash
# After Docker is running (docker compose up -d)
docker compose exec backend python scripts/seed_data.py

# Or locally (with dependencies running)
cd backend && python scripts/seed_data.py
```

### Experience Walkthrough

| Step | Page | What to see |
|------|------|-------------|
| 1 | Login (`/login`) | Login with `admin` / `admin123` |
| 2 | Dashboard (`/`) | 4 stat cards with real data, sentiment pie chart, 30-day trend line, keyword word cloud, latest comments with fake-review markers |
| 3 | Products (`/products`) | 6 products across JD/淘宝 platforms, searchable and filterable |
| 4 | Product Detail | Review list with sentiment analysis per comment |
| 5 | Analysis (`/analysis`) | 3 tasks with different status tags (completed/processing/errors) |
| 6 | Analysis Result | Detailed per-comment analysis results table with progress bar |
| 7 | Comments (`/comments`) | 60+ reviews, sortable and filterable |
| 8 | Crawl (`/crawl`) | Create and manage crawl tasks (try a JD URL: `https://item.jd.com/10000000.html`) |
| 9 | Dashboard auto-refresh | Wait 30s — data refreshes automatically, timestamp updates |

### Demo Data Summary

| Item | Count |
|------|-------|
| Users | 2 (admin + user) |
| Products | 6 (3 JD + 3 Taobao) |
| Comments | 61 (including 5 fake reviews highlighted in red) |
| Analysis Results | 53 across 3 tasks |
| Unanalyzed Comments | 8 (for "pending" demo) |

## Environment Variables

参考 `.env.example` 文件配置：

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://ecommerce:ecommerce_password@localhost:5432/ecommerce_reviews` | 数据库连接 |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis 连接 |
| `JWT_SECRET_KEY` | `jwt-dev-secret` | JWT 密钥 |
| `NLP_MODEL_TYPE` | `bert` | NLP 模型类型 |

## Project Structure

```
├── backend/              # Flask API 服务
│   ├── app/
│   │   ├── api/          # RESTful 路由 (auth, products, comments, analysis, dashboard, crawl)
│   │   ├── crawler/      # 爬虫引擎 (base, anti_bot, adapters/jd)
│   │   ├── models/       # 数据库模型 (User, Product, Comment, CommentAnalysis, AnalysisTask, CrawlTask)
│   │   ├── services/     # 业务逻辑层 (auth, comment, analysis, sentiment, report, data_pipeline)
│   │   ├── tasks/        # Celery 异步任务
│   │   ├── utils/        # 工具函数 (time, response, errors, validators, text_cleaner)
│   │   └── config/       # 配置文件 (Development, Testing, Production)
│   ├── migrations/       # 数据库迁移
│   └── tests/            # 测试 (175 tests: 23 unit + 44 integration + 59 crawler + 49 data_pipeline)
├── frontend/             # Vue 3 前端
│   └── src/
│       ├── views/        # 页面 (Dashboard, Analysis, Products, Comments, Login)
│       ├── components/   # 公共组件 (含组件测试)
│       ├── api/          # API 请求
│       ├── store/        # Pinia 状态
│       └── router/       # 路由配置
├── nlp/                  # NLP 模型模块
│   ├── src/
│   │   ├── data_processing/  # 数据预处理 (cleaner, preprocessor, tokenizer)
│   │   ├── models/           # 模型定义 (BERT, LLM)
│   │   │   ├── bert/         # BERT 情感分类模型
│   │   │   └── llm/          # Qwen2.5 LLM 分析模型
│   │   ├── training/         # 训练流程 (trainer, evaluator, optimizer)
│   │   ├── inference/        # 推理服务 (predictor, postprocessor)
│   │   └── evaluation/       # 评估工具 (metrics, error_analysis)
│   ├── tests/            # NLP 测试 (94 tests: augmenter, training, confusion, model_loading, onnx)
│   └── notebooks/        # Jupyter notebooks
├── scripts/              # 部署脚本
└── docs/                 # 文档 (项目实现方案, 开发日志)
```

## API Overview

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/auth/login` | 用户登录 |
| POST | `/api/v1/auth/refresh` | 刷新令牌 |
| GET | `/api/v1/products` | 商品列表 |
| GET | `/api/v1/products/<id>/comments` | 商品评论 |
| POST | `/api/v1/comments/import` | 导入评论 |
| POST | `/api/v1/analysis/tasks` | 创建分析任务 |
| GET | `/api/v1/analysis/tasks/<id>` | 分析进度 |
| GET | `/api/v1/analysis/dashboard` | 仪表盘数据 |
| GET | `/api/v1/analysis/trend` | 趋势数据 |
| POST | `/api/v1/crawl/tasks` | 创建爬虫任务 |
| GET | `/api/v1/crawl/tasks` | 爬虫任务列表 |
| GET | `/api/v1/crawl/tasks/<id>` | 爬虫任务详情 |
| POST | `/api/v1/crawl/tasks/<id>/start` | 手动启动爬虫 |
| DELETE | `/api/v1/crawl/tasks/<id>` | 删除爬虫任务 |
| GET | `/api/v1/crawl/stats` | 爬虫统计 |

## Test Accounts

| Username | Password | Role |
|---|---|---|
| `admin` | `admin123` | 管理员 |
| `user` | `user123` | 普通用户 |

## Testing

### Backend Tests (201 tests)
```bash
cd backend
pytest tests/ -v
# 23 unit tests (API, Auth, Models) + 44 integration tests (Auth, Products, Comments, Analysis, Dashboard flows) + 59 crawler tests (anti_bot, base, jd_adapter, e2e) + 49 data_pipeline tests (text_cleaner, dedup, integration) + 26 cache tests (utils, dashboard integration)
```

### NLP Tests (94 tests)
```bash
cd nlp
pytest tests/ -v
# Covers cleaner, preprocessor, postprocessor, error analysis, LLM analyzer, metrics, evaluator, augmenter, training, confusion, model_loading, onnx
```

### Frontend Tests (14 tests)
```bash
cd frontend
npm run test
# Component tests for Loading, EmptyState, ErrorState
```

### Full Test Suite (309 tests)
```bash
cd backend && pytest tests/ -v && cd ../nlp && pytest tests/ -v && cd ../frontend && npm run test
```

### Frontend Build
```bash
cd frontend
npm run build
# Vite build (~2322 modules, ~380KB gzip)
```

## License

MIT
