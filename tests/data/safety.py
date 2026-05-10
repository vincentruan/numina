"""安全检测模块 - 防止生产环境误执行"""

import os
import sys
from typing import Optional

# 生产环境数据库特征
PROD_PATTERNS = [
    "prod", "production",
    "rds.amazonaws.com",  # AWS RDS
    "aliyun", "aliyuncs",  # 阿里云
    "tencent", "tencentcdb",  # 腾讯云
    "baidu", "bce",  # 百度云
    "huawei", "huaweicloud",  # 华为云
]


def is_production_db(db_url: str) -> bool:
    """检测是否为生产数据库"""
    url_lower = db_url.lower()
    return any(pattern in url_lower for pattern in PROD_PATTERNS)


def safety_check(db_url: str, force: bool = False) -> bool:
    """
    安全检查
    
    Args:
        db_url: 数据库连接 URL
        force: 是否强制绕过检查
    
    Returns:
        bool: 是否允许继续执行
    """
    if not is_production_db(db_url):
        return True
    
    # 生产库检测
    if force:
        print(f"⚠️  WARNING: 疑似生产数据库: {db_url}")
        print("使用 --force 绕过安全检查")
        
        # 二次确认
        try:
            response = input("确认要在生产数据库执行 seed? [yes/N]: ")
            if response.lower() != "yes":
                print("已取消")
                return False
            print("继续执行...")
            return True
        except (EOFError, KeyboardInterrupt):
            print("\n已取消（非交互环境，使用 --force 需配合 CI 环境变量）")
            return False
    else:
        print(f"ERROR: 疑似生产数据库: {db_url}")
        print("使用 --force 强制继续（不推荐）")
        return False


def check_ci_environment() -> bool:
    """检查是否在 CI/CD 环境"""
    ci_envs = ["CI", "GITHUB_ACTIONS", "GITLAB_CI", "JENKINS_URL", "CIRCLECI"]
    return any(os.getenv(env) for env in ci_envs)
