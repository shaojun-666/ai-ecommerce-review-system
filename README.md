# AI E-commerce Review Analysis System

基于 AI 的电商评论智能分析系统，支持多平台评论采集、情感分析、关键词提取、虚假评论检测等功能。

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
- BERT 中文情感分析模型
- 关键词提取 (TF-IDF / TextRank)
- 虚假评论检测
- 数据分析与可视化 (Pandas / Jupyter)

**DevOps**
- Docker Compose (PostgreSQL, Redis, Backend, Celery, Nginx)
- Gunicorn + Gevent
- Sentry 异常监控

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- Docker & Docker Compose (可选)

### 1. Clone & Setup

```bash
git clone https://github.com/shaojun-666/ai-ecommerce-review-system.git
cd ai-ecommerce-review-system
```

### 2. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Database

使用 Docker 启动 PostgreSQL 和 Redis：

```bash
docker compose up -d postgres redis
```

初始化数据库：

```bash
flask db upgrade
python scripts/seed_data.py
```

### 4. Run Backend

```bash
flask run
# 或使用 gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
```

### 5. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### 6. Start Celery Worker (可选，用于异步分析任务)

```bash
cd backend
celery -A app.tasks worker -l info
```

### 7. Access

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/api/docs

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
│   │   ├── api/          # RESTful 路由
│   │   ├── models/       # 数据库模型
│   │   ├── services/     # 业务逻辑层
│   │   ├── tasks/        # Celery 异步任务
│   │   ├── utils/        # 工具函数
│   │   └── config/       # 配置文件
│   ├── migrations/       # 数据库迁移
│   └── tests/            # 测试
├── frontend/             # Vue 3 前端
│   └── src/
│       ├── views/        # 页面
│       ├── components/   # 公共组件
│       ├── api/          # API 请求
│       ├── store/        # Pinia 状态
│       └── router/       # 路由配置
├── nlp/                  # NLP 模型
│   ├── src/              # 模型代码
│   └── notebooks/        # Jupyter notebooks
├── scripts/              # 部署脚本
└── docs/                 # 文档
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

## Test Accounts

| Username | Password | Role |
|---|---|---|
| `admin` | `admin123` | 管理员 |
| `user` | `user123` | 普通用户 |

## License

MIT
