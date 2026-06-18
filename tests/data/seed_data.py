"""独立测试数据生成脚本

用法:
    python seed_data.py [--force] [--reset] [--skip-demo] [--db-url URL]

选项:
    --force       绕过安全检查
    --reset       清空 seed 账号后重建
    --skip-demo   跳过 demouser 创建
    --db-url      指定数据库 URL

环境变量:
    TEST_DATABASE_URL   测试数据库 URL
    DATABASE_URL        备选数据库 URL
"""

import argparse
import os
import sys
from pathlib import Path

# 添加当前目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from db import Base, init_engine, init_session_factory, get_db_session
from safety import safety_check

# 导入场景
from scenarios.empty import seed_empty_scenario
from scenarios.single_asset import seed_single_asset_scenario
from scenarios.full import seed_full_scenario
from scenarios.demo import seed_demo_scenario


def parse_args():
    parser = argparse.ArgumentParser(
        description="Numina 仿真测试数据生成脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python seed_data.py                    # 创建所有测试账号
    python seed_data.py --force           # 绕过安全检查
    python seed_data.py --skip-demo     # 仅创建固定测试账号
    python seed_data.py --db-url sqlite:///test.db
        """
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="绕过生产库安全检查"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="清空所有 seed 账号及数据后重建"
    )
    parser.add_argument(
        "--skip-demo",
        action="store_true",
        help="跳过 demouser 完整数据生成"
    )
    parser.add_argument(
        "--db-url",
        type=str,
        help="数据库连接 URL（覆盖环境变量）"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="详细输出"
    )
    return parser.parse_args()


SEED_USERNAMES = ["test_empty", "test_asset", "test_rich", "demouser", "demouser_spouse"]


# Authoritative credential map for seed accounts. Used to re-sync passwords
# and PINs on every seed run so stale hashes (e.g. from bind-mounted SQLite
# that survives `docker compose down -v`) don't block login. Keys are usernames
# for adults; child entries are matched by (family_owner_username, display_name)
# since children may have null username.
_ADULT_CREDENTIALS: dict[str, str] = {
    "test_empty": "TestEmpty123!",
    "test_asset": "TestAsset123!",
    "test_rich": "TestRich123!",
    "demouser": "DemoPass123",
    "demouser_spouse": "DemoPass123",
}

# (owner_username, child_display_name) → (password, pin)
_CHILD_CREDENTIALS: dict[tuple[str, str], tuple[str, str]] = {
    ("test_rich", "test_child"): ("TestRich123!", "🐱🐶🌟🌈"),
    ("demouser", "小宝"): ("DemoPass123", "🐱🐶🌟🌈"),
    ("demouser", "大宝"): ("DemoPass123", "🐱🐶🌟🌈"),
}


def _sync_seed_credentials(db) -> None:
    """Re-hash passwords and PINs for known seed accounts.

    Runs before scenarios so that pre-existing rows (e.g. from a bind-mounted
    SQLite DB that wasn't cleared by `docker compose down -v`) get fresh
    credential hashes matching the current seed definitions. Skips silently
    when an account doesn't exist yet — the scenario will create it.
    """
    from factories.users import _hash

    print("【Sync】对齐 seed 账号凭据...")

    updated = 0
    for username, password in _ADULT_CREDENTIALS.items():
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            continue
        user.password_hash = _hash(password)
        updated += 1

    for (owner_username, display_name), (password, pin) in _CHILD_CREDENTIALS.items():
        owner = db.query(User).filter(User.username == owner_username).first()
        if owner is None or not owner.family_id:
            continue
        child = (
            db.query(User)
            .filter(
                User.family_id == owner.family_id,
                User.display_name == display_name,
                User.role == "child",
            )
            .first()
        )
        if child is None:
            continue
        child.password_hash = _hash(password)
        child.pin_hash = _hash(pin)
        updated += 1

    db.flush()
    print(f"  [ok] 已对齐 {updated} 个账号的凭据\n")


def _reset_seed_accounts(db) -> None:
    """删除所有 seed 账号及其家庭数据，允许场景重新创建。"""
    from sqlalchemy import text

    print("【Reset】清空 seed 账号数据...\n")

    users = db.query(User).filter(User.username.in_(SEED_USERNAMES)).all()
    if not users:
        print("  (无 seed 账号，跳过 reset)")
        return

    family_ids = list({u.family_id for u in users if u.family_id})
    user_ids = [u.id for u in users]

    def _del(table: str, col: str, vals: list) -> None:
        if not vals:
            return
        placeholders = ",".join(str(v) for v in vals)
        db.execute(text(f"DELETE FROM {table} WHERE {col} IN ({placeholders})"))

    if not user_ids or not family_ids:
        print("  (无 seed 账号，跳过 reset)")
        return

    uid_list = ",".join(str(v) for v in user_ids)
    fid_list = ",".join(str(v) for v in family_ids)

    # Join tables — delete via subquery (no direct family_id/user_id column)
    db.execute(text(
        f"DELETE FROM asset_tags WHERE asset_id IN "
        f"(SELECT id FROM assets WHERE user_id IN ({uid_list}))"
    ))
    db.execute(text(
        f"DELETE FROM chore_template_assignees WHERE template_id IN "
        f"(SELECT id FROM chore_templates WHERE family_id IN ({fid_list}))"
    ))

    # Tables with family_id
    for table in ["coin_transactions", "chore_instances", "chore_templates",
                  "child_wishes", "blind_box_gifts", "blind_box_config", "bonus_draws"]:
        db.execute(text(f"DELETE FROM {table} WHERE family_id IN ({fid_list})"))

    # Tables with user_id
    for table in ["wishes", "liabilities", "assets"]:
        db.execute(text(f"DELETE FROM {table} WHERE user_id IN ({uid_list})"))

    # Child users in these families
    db.execute(text(f"DELETE FROM users WHERE family_id IN ({fid_list}) AND role = 'child'"))

    # Seed users and their families
    name_list = ",".join(f"'{n}'" for n in SEED_USERNAMES)
    db.execute(text(f"DELETE FROM users WHERE username IN ({name_list})"))
    db.execute(text(f"DELETE FROM families WHERE id IN ({fid_list})"))

    db.flush()
    print(f"  [ok] 已清空 {len(users)} 个 seed 账号及关联数据\n")


# Import User for reset function
from models import User  # noqa: E402


def main():
    args = parse_args()
    
    # 获取数据库 URL
    db_url = args.db_url or os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: 未指定数据库 URL")
        print("请设置 TEST_DATABASE_URL 或使用 --db-url")
        sys.exit(1)
    
    print(f"数据库: {db_url}")
    
    # 安全检查
    if not safety_check(db_url, force=args.force):
        sys.exit(1)
    
    # 初始化数据库连接
    engine = init_engine(db_url)
    init_session_factory(engine)

    # 创建所有表（models.py 使用独立的 Base）
    Base.metadata.create_all(bind=engine)

    # 创建 session
    db = get_db_session()
    
    try:
        print("\n" + "="*50)
        print("Numina 仿真测试数据生成")
        print("="*50 + "\n")

        # --reset: 删除所有 seed 账号及其关联数据，让场景重新创建
        if args.reset:
            _reset_seed_accounts(db)

        # 对齐已有 seed 账号的凭据（修复 bind mount 导致的 stale hash）
        if not args.reset:
            _sync_seed_credentials(db)

        # Part 1: 固定测试账号
        print("【Part 1】固定测试账号\n")

        seed_empty_scenario(db, verbose=args.verbose)
        seed_single_asset_scenario(db, verbose=args.verbose)
        seed_full_scenario(db, verbose=args.verbose)
        
        # Part 2: demouser（可选）
        if not args.skip_demo:
            print("\n" + "-"*50)
            print("\n【Part 2】demouser 完整仿真数据\n")
            seed_demo_scenario(db, verbose=args.verbose)
        else:
            print("\n【Part 2】跳过 demouser (--skip-demo)")
        
        # 提交事务
        db.commit()
        
        print("\n" + "="*50)
        print("✓ Seed 完成！")
        print("="*50)
        
        print("\n测试账号:")
        print("  test_empty  / TestEmpty123!  - 空家庭")
        print("  test_asset  / TestAsset123!  - 单资产")
        print("  test_rich   / TestRich123!   - 完整数据")
        if not args.skip_demo:
            print("  demouser    / DemoPass123    - 完整仿真")
        
    except Exception as e:
        db.rollback()
        print(f"\n✗ Seed 失败: {e}")
        import traceback
        if args.verbose:
            traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
