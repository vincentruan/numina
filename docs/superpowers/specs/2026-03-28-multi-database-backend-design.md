# Multi-Database Backend Support Design

**Date:** 2026-03-28
**Status:** Approved
**Scope:** Backend 模块数据库层统一抽象，支持 SQLite、MySQL、PostgreSQL 三种数据库，默认 SQLite

---

## Core Goal

统一抽象数据库层操作，通过 `DATABASE_URL` 环境变量自动识别数据库类型，支持多种 RDBMS，便于在不同部署场景下切换数据库后端。

---

## Design Decisions

### 支持的数据库类型
- SQLite（默认）
- MySQL
- PostgreSQL

### 数据库切换方式
- 环境变量驱动：仅通过 `DATABASE_URL` 切换（如 `mysql://...`、`postgresql://...`），自动识别方言

### 异步/同步模式
- 保持同步模式，改动最小，对当前规模足够

### Docker 部署
- 默认 SQLite，提供可选的 MySQL/PostgreSQL 服务定义（通过 Docker profiles 切换）

---

## Directory Structure

新增 `backend/app/db/` 模块：

```
backend/app/db/
├── __init__.py          # 导出 get_engine, get_session_factory
├── backend.py           # DatabaseBackend 抽象基类
├── sqlite.py            # SQLiteBackend 实现
├── mysql.py             # MySQLBackend 实现
├── postgres.py          # PostgreSQLBackend 实现
└── factory.py           # create_backend(url) -> DatabaseBackend
```

---

## Core Abstraction

### DatabaseBackend 抽象基类

```python
from abc import ABC, abstractmethod
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

class DatabaseBackend(ABC):
    """数据库后端抽象基类"""
    
    @abstractmethod
    def create_engine(self, url: str) -> Engine:
        """创建 SQLAlchemy Engine"""
        pass
    
    @abstractmethod
    def get_connection_args(self) -> dict:
        """返回数据库特定的连接参数"""
        pass
    
    @abstractmethod
    def get_pool_config(self) -> dict:
        """返回连接池配置（pool_size, pool_recycle 等）"""
        pass
    
    def create_session_factory(self, engine: Engine) -> sessionmaker:
        """创建 Session 工厂（通用实现）"""
        return sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

### Backend 实现类

- **SQLiteBackend**: 返回 `check_same_thread=False`，无连接池
- **MySQLBackend**: 返回连接池配置（pool_size=10, pool_recycle=3600）
- **PostgreSQLBackend**: 返回连接池配置（pool_size=10）

---

## Factory Function

```python
from sqlalchemy.engine.url import make_url
from .backend import DatabaseBackend
from .sqlite import SQLiteBackend
from .mysql import MySQLBackend
from .postgres import PostgreSQLBackend

BACKEND_MAP = {
    "sqlite": SQLiteBackend,
    "mysql": MySQLBackend,
    "mysql+aiomysql": MySQLBackend,
    "postgresql": PostgreSQLBackend,
    "postgresql+psycopg2": PostgreSQLBackend,
}

def create_backend(url: str) -> DatabaseBackend:
    """根据 DATABASE_URL 创建对应的 Backend"""
    parsed = make_url(url)
    dialect = parsed.drivername
    
    base_dialect = dialect.split("+")[0] if "+" in dialect else dialect
    
    if base_dialect not in BACKEND_MAP:
        raise ValueError(f"不支持的数据库类型: {dialect}")
    
    return BACKEND_MAP[base_dialect]()

def get_engine(url: str) -> Engine:
    """便捷函数：直接返回 Engine"""
    backend = create_backend(url)
    return backend.create_engine(url)
```

---

## Existing Files Changes

### database.py

简化为调用工厂：

```python
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import settings
from app.db import get_engine

engine = get_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### alembic/env.py

复用工厂：

```python
from app.db import get_engine
from app.config import settings
from app.database import Base

def run_migrations_online() -> None:
    connectable = get_engine(settings.DATABASE_URL)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()
```

---

## Docker Compose

添加可选的 MySQL/PostgreSQL 服务：

```yaml
services:
  mysql:
    image: ${X_DOCKER_MIRROR:-docker.xuanyuan.me}/library/mysql:8.0
    profiles:
      - mysql
    environment:
      - MYSQL_DATABASE=numina
      - MYSQL_USER=numina
      - MYSQL_PASSWORD=numinapass
    volumes:
      - mysql_data:/var/lib/mysql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]

  postgres:
    image: ${X_DOCKER_MIRROR:-docker.xuanyuan.me}/library/postgres:15
    profiles:
      - postgres
    environment:
      - POSTGRES_DB=numina
      - POSTGRES_USER=numina
      - POSTGRES_PASSWORD=numinapass
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U numina"]

volumes:
  mysql_data:
  postgres_data:
```

**使用方式：**
```bash
# 默认 SQLite
docker-compose up -d

# 使用 MySQL
docker-compose --profile mysql up -d
DATABASE_URL=mysql+pymysql://numina:numinapass@mysql:3306/numina

# 使用 PostgreSQL
docker-compose --profile postgres up -d
DATABASE_URL=postgresql+psycopg2://numina:numinapass@postgres:5432/numina
```

---

## Integration Tests

新增 `backend/tests/integration/` 目录：

```
backend/tests/integration/
├── conftest.py          # Docker 容器启动 fixture
├── test_mysql.py        # MySQL 集成测试
└── test_postgres.py     # PostgreSQL 集成测试
```

**测试用例：**
- 连接建立测试
- 基本 CRUD 操作
- Alembic 迁移执行测试
- 数据库特定功能验证

通过 `pytest -m integration` 标记运行。

---

## Dependencies

`pyproject.toml` 新增：

```toml
[project]
dependencies = [
    # 新增数据库驱动
    "aiomysql>=0.2.0",
    "psycopg2-binary>=2.9.9",
]

[dependency-groups]
dev = [
    # 新增集成测试依赖
    "docker>=7.0.0",
]
```

---

## Acceptance Criteria

| 项目 | 验收方式 |
|------|----------|
| A. 单元测试通过 | `uv run pytest tests/ -v` |
| B. 集成测试 | `uv run pytest -m integration -v` |
| C. Alembic迁移 | 三种数据库的 `alembic upgrade head` |
| D. Docker切换 | `--profile mysql` / `--profile postgres` 启动验证 |
| E. 文档更新 | CLAUDE.md 新增数据库配置说明 |

---

## Implementation Steps

1. 创建 `backend/app/db/` 模块（backend.py, sqlite.py, mysql.py, postgres.py, factory.py, __init__.py）
2. 改造 `database.py`
3. 改造 `alembic/env.py`
4. 更新 `pyproject.toml` 依赖
5. 更新 `docker-compose.yml`
6. 创建集成测试
7. 运行验收测试
8. 更新文档