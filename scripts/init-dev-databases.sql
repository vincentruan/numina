-- ============================================================================
-- Dev/Test 初始化脚本 — 创建 numina_dev 和 numina_test 数据库
-- 仅由 docker-entrypoint-initdb.d 在首次启动时执行
-- ============================================================================

-- 创建开发数据库
SELECT 'CREATE DATABASE numina_dev OWNER numina'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'numina_dev')\gexec

-- 创建测试数据库
SELECT 'CREATE DATABASE numina_test OWNER numina'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'numina_test')\gexec

-- 验证
\l
