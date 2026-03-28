"""PostgreSQL 集成测试"""

import pytest
from sqlalchemy import text

from app.db import get_engine, create_backend, PostgreSQLBackend


pytestmark = pytest.mark.integration


class TestPostgreSQLBackend:
    """PostgreSQL Backend 测试"""

    def test_create_backend_postgres(self, postgres_url):
        """测试创建 PostgreSQL Backend"""
        backend = create_backend(postgres_url)
        assert isinstance(backend, PostgreSQLBackend)

    def test_postgres_connection(self, postgres_url):
        """测试 PostgreSQL 连接建立"""
        engine = get_engine(postgres_url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

    def test_postgres_pool_config(self):
        """测试 PostgreSQL 连接池配置"""
        backend = PostgreSQLBackend()
        pool_config = backend.get_pool_config()
        assert pool_config["pool_size"] == 10
        assert pool_config["pool_pre_ping"] is True

    def test_postgres_create_table(self, postgres_url):
        """测试 PostgreSQL 表创建"""
        engine = get_engine(postgres_url)
        with engine.connect() as conn:
            conn.execute(text("CREATE TABLE IF NOT EXISTS test_table (id INT PRIMARY KEY)"))
            conn.execute(text("INSERT INTO test_table VALUES (1)"))
            result = conn.execute(text("SELECT id FROM test_table"))
            assert result.scalar() == 1
            conn.execute(text("DROP TABLE test_table"))