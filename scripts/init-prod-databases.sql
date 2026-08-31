-- ============================================================================
-- 本地生产备库初始化脚本 — 创建 numina_prod 和 numina_prod_deerflow 数据库
-- 仅由 docker-entrypoint-initdb.d 在首次启动时执行
--
-- ⚠️ 此脚本仅创建生产级数据库，绝不触碰 dev/test 数据库
-- ============================================================================

-- 创建主应用数据库
SELECT 'CREATE DATABASE numina_prod OWNER numina'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'numina_prod')\gexec

-- 创建 DeerFlow checkpoint 数据库（独立库，避免 alembic_version 冲突）
SELECT 'CREATE DATABASE numina_prod_deerflow OWNER numina'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'numina_prod_deerflow')\gexec

-- 验证
\l
