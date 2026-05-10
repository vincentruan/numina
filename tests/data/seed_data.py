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

from db import init_engine, init_session_factory, get_db_session
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
    
    # 创建 session
    db = get_db_session()
    
    try:
        print("\n" + "="*50)
        print("Numina 仿真测试数据生成")
        print("="*50 + "\n")
        
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
