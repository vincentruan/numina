#!/usr/bin/env python3
"""Generate .env file with auto-generated security keys.

Usage:
    python scripts/generate_env.py [--dev] [--domain DOMAIN]

Called by `make setup-env`. Not intended to be run directly by users.
"""
import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


def generate_hex_key() -> str:
    import subprocess
    return subprocess.check_output(["openssl", "rand", "-hex", "32"]).decode().strip()


def generate_fernet_key() -> str:
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate .env for Numina")
    parser.add_argument("--dev", action="store_true", help="Development mode")
    parser.add_argument("--domain", default="localhost", help="Production domain for CORS")
    args = parser.parse_args()

    env = "development" if args.dev else "production"

    secret_key = generate_hex_key()
    altcha_hmac_key = generate_hex_key()
    ai_encryption_key = generate_fernet_key()
    agent_internal_token = generate_hex_key()
    storage_encryption_key = generate_fernet_key()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if args.dev:
        cors = '["http://localhost:5173","http://localhost:5174","http://localhost:80","http://localhost:28080"]'
    else:
        cors = f'["http://localhost","http://localhost:80","https://{args.domain}"]'

    content = f"""\
# Numina Environment Configuration
# 自动生成于 {now}

# 环境模式 (production / development)
ENVIRONMENT={env}

# 数据库 (默认 SQLite; 可选 mysql/postgres，需运行 make setup-db-mysql/postgres)
DATABASE_URL=sqlite:////app/.numina/data/db/numina.db

# CORS 域名 (JSON 数组格式，生产环境不可为 ["*"])
CORS_ORIGINS={cors}

# JWT 过期时间
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# 安全密钥
SECRET_KEY={secret_key}
ALTCHA_HMAC_KEY={altcha_hmac_key}
AI_ENCRYPTION_KEY={ai_encryption_key}
AGENT_INTERNAL_TOKEN={agent_internal_token}
STORAGE_ENCRYPTION_KEY={storage_encryption_key}

# 初始化邀请码 (逗号分隔，首次部署后可通过 make setup-invitation-codes 生成更多)
INIT_INVITATION_CODES=

# 可选：MySQL/PostgreSQL 凭据 (使用对应 DB 时取消注释)
# MYSQL_ROOT_PASSWORD=
# MYSQL_DATABASE=numina
# MYSQL_USER=numina
# MYSQL_PASSWORD=
# POSTGRES_DB=numina
# POSTGRES_USER=numina
# POSTGRES_PASSWORD=
"""

    ENV_FILE.write_text(content)
    print(f"✓ .env 已创建 ({env} 模式)")


if __name__ == "__main__":
    main()
