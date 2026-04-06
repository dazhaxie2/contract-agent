#!/bin/bash
# 数据库初始化脚本
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- 启用扩展
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    CREATE EXTENSION IF NOT EXISTS "pg_trgm";

    -- 创建全文搜索配置
    -- (表结构由SQLAlchemy/Alembic自动创建)

    SELECT 'Database initialized successfully' AS status;
EOSQL
