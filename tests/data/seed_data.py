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

from sqlalchemy import inspect, text

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
    """删除所有 seed 账号及其关联数据，允许场景重新创建。"""
    from sqlalchemy import inspect as sa_inspect

    print("【Reset】清空 seed 账号数据...\n")

    users = db.query(User).filter(User.username.in_(SEED_USERNAMES)).all()
    if not users:
        print("  (无 seed 账号，跳过 reset)")
        return

    family_ids = list({u.family_id for u in users if u.family_id})
    user_ids = [u.id for u in users]

    if not user_ids or not family_ids:
        print("  (无 seed 账号，跳过 reset)")
        return

    uid_text_list = ",".join(f"'{v}'" for v in user_ids)
    fid_text_list = ",".join(f"'{v}'" for v in family_ids)
    name_list = ",".join(f"'{n}'" for n in SEED_USERNAMES)

    engine = db.get_bind()
    inspector = sa_inspect(engine)
    all_tables = set(inspector.get_table_names())
    db_url = str(engine.url)

    # 收集每个表的列，用于生成 DELETE 语句
    table_columns: dict[str, set[str]] = {}
    for table in all_tables:
        table_columns[table] = {c["name"] for c in inspector.get_columns(table)}

    # 先处理没有直接 family_id/user_id 列、但引用 assets/wishes/users 的关联表
    join_cleanup = [
        ("asset_tags", "asset_id", "assets", "user_id", uid_text_list),
        ("chore_template_assignees", "template_id", "chore_templates", "family_id", fid_text_list),
        ("wish_savings_logs", "wish_id", "wishes", "user_id", uid_text_list),
    ]
    for table, col, parent_table, parent_filter_col, parent_filter_list in join_cleanup:
        if table not in all_tables or parent_table not in all_tables:
            continue
        db.execute(text(
            f"DELETE FROM {table} WHERE CAST({col} AS TEXT) IN "
            f"(SELECT CAST(id AS TEXT) FROM {parent_table} WHERE CAST({parent_filter_col} AS TEXT) IN ({parent_filter_list}))"
        ))

    def _delete_by_seed_ids() -> None:
        """删除所有带 family_id / user_id / child_user_id 的 seed 相关行。"""
        for table, cols in table_columns.items():
            if table in ("users", "families"):
                continue
            if "family_id" in cols:
                db.execute(text(
                    f"DELETE FROM {table} WHERE CAST(family_id AS TEXT) IN ({fid_text_list})"
                ))
            elif "user_id" in cols:
                db.execute(text(
                    f"DELETE FROM {table} WHERE CAST(user_id AS TEXT) IN ({uid_text_list})"
                ))
            elif "child_user_id" in cols:
                db.execute(text(
                    f"DELETE FROM {table} WHERE CAST(child_user_id AS TEXT) IN "
                    f"(SELECT CAST(id AS TEXT) FROM users WHERE family_id IN ({fid_text_list}) AND role = 'child')"
                ))

    if db_url.startswith("postgresql"):
        # Postgres: 临时禁用触发器和 FK 检查，直接按 id 清理，避免复杂拓扑排序
        db.execute(text("SET session_replication_role = replica"))
        try:
            _delete_by_seed_ids()
            db.execute(text(f"DELETE FROM users WHERE family_id IN ({fid_text_list}) AND role = 'child'"))
            db.execute(text(f"DELETE FROM users WHERE username IN ({name_list})"))
            db.execute(text(f"DELETE FROM families WHERE id IN ({fid_text_list})"))
        finally:
            db.execute(text("SET session_replication_role = DEFAULT"))
    else:
        # SQLite / other: 使用外键拓扑排序清理
        target_tables: list[str] = []
        for table, cols in table_columns.items():
            if table in ("users", "families"):
                continue
            if cols & {"family_id", "user_id", "child_user_id"}:
                target_tables.append(table)

        dependencies: dict[str, set[str]] = {t: set() for t in all_tables}
        for table in all_tables:
            for fk in inspector.get_foreign_keys(table):
                ref_table = fk.get("referred_table")
                if ref_table and table in all_tables and ref_table in all_tables:
                    dependencies[table].add(ref_table)

        target_set = set(target_tables)
        visited: set[str] = set()
        dfs_order: list[str] = []

        def visit(t: str) -> None:
            if t in visited or t not in target_set:
                return
            visited.add(t)
            for dep in dependencies.get(t, set()):
                if dep in target_set:
                    visit(dep)
            dfs_order.append(t)

        for t in sorted(target_tables):
            visit(t)

        ordered = list(reversed(dfs_order))

        for table in ordered:
            cols = table_columns[table]
            if "family_id" in cols:
                db.execute(text(
                    f"DELETE FROM {table} WHERE CAST(family_id AS TEXT) IN ({fid_text_list})"
                ))
            elif "user_id" in cols:
                db.execute(text(
                    f"DELETE FROM {table} WHERE CAST(user_id AS TEXT) IN ({uid_text_list})"
                ))
            elif "child_user_id" in cols:
                db.execute(text(
                    f"DELETE FROM {table} WHERE CAST(child_user_id AS TEXT) IN "
                    f"(SELECT CAST(id AS TEXT) FROM users WHERE family_id IN ({fid_text_list}) AND role = 'child')"
                ))

        db.execute(text(f"DELETE FROM users WHERE family_id IN ({fid_text_list}) AND role = 'child'"))
        db.execute(text(f"DELETE FROM users WHERE username IN ({name_list})"))
        db.execute(text(f"DELETE FROM families WHERE id IN ({fid_text_list})"))

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

        # Postgres 下场景创建第一个 owner 时存在 users/families 循环外键：
        # user.family_id 指向 family，family.created_by 指向 user。
        # 场景先用 family_id=0 占位创建 user，再创建 family，最后修正 family_id。
        # 临时禁用触发器/FK 检查，等所有场景跑完再恢复，避免插入 family_id=0 时报错。
        postgres_mode = db_url.startswith("postgresql")
        if postgres_mode:
            db.execute(text("SET session_replication_role = replica"))

        try:
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
        finally:
            if postgres_mode:
                db.execute(text("SET session_replication_role = DEFAULT"))

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
