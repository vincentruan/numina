"""仅 seed 家庭约定（manifesto）记录 — 不影响其他测试数据。

用法:
    python seed_manifesto.py [--force] [--db-url URL]

前提: demouser / test_rich 等 seed 账号已存在（由 seed_data.py 创建）。
      本脚本只为已有家庭补建 manifesto 记录，幂等安全。
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from db import Base, init_engine, init_session_factory, get_db_session
from safety import safety_check
from models import User
from factories.manifesto import ManifestoFactory


def parse_args():
    parser = argparse.ArgumentParser(description="仅 seed 家庭约定记录")
    parser.add_argument("--force", action="store_true", help="绕过生产库安全检查")
    parser.add_argument("--db-url", type=str, help="数据库连接 URL（覆盖环境变量）")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    return parser.parse_args()


def main():
    args = parse_args()

    db_url = args.db_url or os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: 未指定数据库 URL")
        print("请设置 TEST_DATABASE_URL 或使用 --db-url")
        sys.exit(1)

    print(f"数据库: {db_url}")

    if not safety_check(db_url, force=args.force):
        sys.exit(1)

    engine = init_engine(db_url)
    init_session_factory(engine)
    Base.metadata.create_all(bind=engine)

    db = get_db_session()
    try:
        print("\n【Manifesto-only seed】\n")

        # ── demouser 家庭 ──────────────────────────────────────────────
        demo_user = db.query(User).filter(User.username == "demouser").first()
        if demo_user and demo_user.family_id:
            manifesto, created = ManifestoFactory.get_or_create(
                db,
                family_id=demo_user.family_id,
                created_by=demo_user.id,
                title="演示家庭约定",
                body="我们约定：\n1. 互相尊重，彼此倾听\n2. 共同分担家务\n3. 每周一次家庭活动\n4. 理性消费，共同储蓄\n5. 关爱彼此，共同成长",
            )
            action = "新建" if created else "已存在"
            print(f"  [ok] demouser 家庭约定 — {action}")

            # 小宝签署（无论 manifesto 新建还是已存在，都确保签署）
            if manifesto.current_version_id:
                child = (
                    db.query(User)
                    .filter(
                        User.family_id == demo_user.family_id,
                        User.display_name == "小宝",
                        User.role == "child",
                    )
                    .first()
                )
                if child:
                    _, sig_created = ManifestoFactory.sign(
                        db,
                        version_id=manifesto.current_version_id,
                        user_id=child.id,
                    )
                    if sig_created:
                        print(f"  [ok] 小宝已签署约定")
                    else:
                        print(f"  [ok] 小宝签署已存在")
        else:
            print("  [skip] demouser 不存在，请先运行 seed_data.py")

        # ── test_rich 家庭 ─────────────────────────────────────────────
        rich_user = db.query(User).filter(User.username == "test_rich").first()
        if rich_user and rich_user.family_id:
            manifesto, created = ManifestoFactory.get_or_create(
                db,
                family_id=rich_user.family_id,
                created_by=rich_user.id,
                title="测试家庭约定",
                body="我们约定：\n1. 互相尊重\n2. 共同分担\n3. 理性消费",
            )
            action = "新建" if created else "已存在"
            print(f"  [ok] test_rich 家庭约定 — {action}")
        else:
            print("  [skip] test_rich 不存在，请先运行 seed_data.py")

        db.commit()
        print("\n✓ Manifesto seed 完成！")

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
