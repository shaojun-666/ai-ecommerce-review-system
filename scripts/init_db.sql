-- Database initialization for AI E-commerce Review Analysis System
-- PostgreSQL 15

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user' CHECK (role IN ('admin', 'user')),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Products table
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    platform VARCHAR(50) DEFAULT '',
    platform_product_id VARCHAR(128) DEFAULT '',
    url VARCHAR(1024) DEFAULT '',
    image_url VARCHAR(1024) DEFAULT '',
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_products_platform_product_id ON products(platform_product_id);
CREATE INDEX IF NOT EXISTS idx_products_user ON products(user_id);
CREATE INDEX IF NOT EXISTS idx_products_platform ON products(platform);

-- Comments table
CREATE TABLE IF NOT EXISTS comments (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    content TEXT NOT NULL,
    content_hash VARCHAR(64) DEFAULT '',
    rating SMALLINT CHECK (rating >= 1 AND rating <= 5),
    author_name VARCHAR(100) DEFAULT '',
    platform VARCHAR(50) DEFAULT '',
    source VARCHAR(50) DEFAULT 'import',
    purchase_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_comments_product ON comments(product_id);
CREATE INDEX IF NOT EXISTS idx_comments_created ON comments(created_at);
CREATE INDEX IF NOT EXISTS idx_comments_product_created ON comments(product_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_comments_rating ON comments(rating);
CREATE INDEX IF NOT EXISTS idx_comments_content_hash ON comments(content_hash);
CREATE INDEX IF NOT EXISTS idx_comments_hash_product ON comments(content_hash, product_id);

-- Analysis tasks table
CREATE TABLE IF NOT EXISTS analysis_tasks (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    name VARCHAR(256) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'completed_with_errors')),
    total_count INTEGER DEFAULT 0,
    processed_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    timeout_at TIMESTAMP,
    result_summary JSONB,
    celery_task_id VARCHAR(128),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tasks_user_status ON analysis_tasks(user_id, status);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON analysis_tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created ON analysis_tasks(created_at);

-- Comment analysis results table
CREATE TABLE IF NOT EXISTS comment_analyses (
    id SERIAL PRIMARY KEY,
    comment_id INTEGER NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
    task_id INTEGER REFERENCES analysis_tasks(id) ON DELETE SET NULL,
    sentiment VARCHAR(16),
    sentiment_score DOUBLE PRECISION,
    aspects JSONB,
    keywords JSONB,
    summary TEXT,
    fake_score DOUBLE PRECISION,
    model_version VARCHAR(64),
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(comment_id)
);
CREATE INDEX IF NOT EXISTS idx_analyses_task ON comment_analyses(task_id);
CREATE INDEX IF NOT EXISTS idx_analyses_sentiment ON comment_analyses(sentiment);
CREATE INDEX IF NOT EXISTS idx_analyses_fake ON comment_analyses(fake_score);
CREATE INDEX IF NOT EXISTS idx_analyses_comment ON comment_analyses(comment_id);

-- Default admin user (password: admin123)
INSERT INTO users (username, email, password_hash, role)
VALUES ('admin', 'admin@example.com',
        'scrypt:32768:8:1$yLhZTf3axooFQ6X4$b7b1d7f1e5a7d6b6c7a5130c30e8d7a6e3d0a3b8c5f6e7d8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f',
        'admin')
ON CONFLICT (username) DO NOTHING;

-- Default user (password: user123)
INSERT INTO users (username, email, password_hash, role)
VALUES ('user', 'user@example.com',
        'scrypt:32768:8:1$yLhZTf3axooFQ6X4$b7b1d7f1e5a7d6b6c7a5130c30e8d7a6e3d0a3b8c5f6e7d8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f',
        'user')
ON CONFLICT (username) DO NOTHING;
