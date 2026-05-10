#!/bin/bash
# seed-data.sh — 仿真测试数据生成入口脚本
#
# 调用独立的 Python 脚本，支持 SQLite/MySQL/PostgreSQL
#
# 用法:
#   ./seed-data.sh [--force] [--reset] [--skip-demo] [--db-url URL]
#
# 选项:
#   --force       绕过安全检查
#   --reset       清空 seed 账号后重建
#   --skip-demo   跳过 demouser 创建
#   --db-url URL  指定数据库 URL
#
# 环境变量:
#   TEST_DATABASE_URL   测试数据库 URL
#   DATABASE_URL        备选数据库 URL

set -euo pipefail

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# 解析参数
ARGS=()
DB_URL=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --force|--reset|--skip-demo|--verbose|-v)
            ARGS+=("$1")
            shift
            ;;
        --db-url)
            DB_URL="$2"
            ARGS+=("$1" "$2")
            shift 2
            ;;
        --help|-h)
            cat <<EOF
用法: $(basename "$0") [选项]

选项:
    --force           绕过安全检查
    --reset           清空 seed 账号后重建
    --skip-demo       跳过 demouser 创建
    --db-url URL      指定数据库 URL
    --verbose, -v     详细输出
    --help, -h        显示帮助

环境变量:
    TEST_DATABASE_URL   测试数据库 URL
    DATABASE_URL        备选数据库 URL

示例:
    ./seed-data.sh                    # 本地 SQLite
    ./seed-data.sh --force           # 绕过安全检查
    ./seed-data.sh --skip-demo     # 仅固定测试账号
EOF
            exit 0
            ;;
        *)
            echo "错误: 未知参数 $1" >&2
            echo "使用 --help 查看用法" >&2
            exit 1
            ;;
    esac
done

# 检测运行环境，选择 Python 执行方式
PYTHON_CMD=""

if [[ -n "${VIRTUAL_ENV:-}" ]] || command -v uv &> /dev/null; then
    # 本地 uv 环境
    if command -v uv &> /dev/null; then
        PYTHON_CMD="uv run python"
    else
        PYTHON_CMD="python"
    fi
elif docker ps 2>/dev/null | grep -q "numina-backend"; then
    # Docker 容器环境
    echo "检测到 Docker 容器，使用容器内 Python..."
    PYTHON_CMD="docker exec -i numina-backend uv run python"
else
    # 默认本地 Python
    PYTHON_CMD="python3"
fi

echo "执行: ${PYTHON_CMD} ${SCRIPT_DIR}/seed_data.py ${ARGS[*]:-}"
echo ""

# 切换工作目录
cd "${SCRIPT_DIR}"

# 执行 Python 脚本
exec ${PYTHON_CMD} "${SCRIPT_DIR}/seed_data.py" "${ARGS[@]:-}"
