#!/usr/bin/env bash
# scripts/dev/dev-all.sh — Launch all Numina dev servers
#
# Usage:
#   make dev-all                              # default: tmux, console only
#   make dev-all MODE=tmux                    # tmux split panes (default)
#   make dev-all MODE=term                    # separate terminal windows
#   make dev-all MODE=bg                      # all background, shell redirect
#   make dev-all LOG=1                        # Python services → log files
#   make dev-all MODE=bg LOG=1               # background + log files
#   make dev-all DB=pgsql                     # use PostgreSQL instead of SQLite
#   make dev-all CACHE=redis                  # use Redis instead of in-memory
#   make dev-all DB=pgsql CACHE=redis         # both
#   DEV_MODE=bg DEV_LOG=1 make dev-all        # env-var form
#
# Parameters:
#   MODE   — tmux (default) | term | bg
#   LOG    — 0 (default, console only) | 1 (Python services → server/.dev-logs/)
#   DB     — sqlite (default) | pgsql
#   CACHE  — memory (default) | redis
#
# Priority (auto-detect when MODE not set):
#   1. tmux  → single session, 5 panes in 3+2 layout
#   2. GUI terminal (macOS Terminal/iTerm2, Linux x-terminal-emulator)
#              → 5 separate terminal windows
#   3. Background + shell stdout redirect (last resort)
#
# When LOG=1, Python services (backend/agent/worker) write logs to
# server/.dev-logs/<service>.log via the existing setup_logging() component.
# Frontend processes (vite) always log to stdout regardless of LOG.
#
# Layout (tmux, 上三下二):
#   ┌──────────┬──────────┬──────────┐
#   │ backend  │  agent   │  worker  │
#   │  :8000   │  :8001   │  :8002   │
#   ├───────────┴────┬─────┴──────────┤
#   │   frontend     │     child      │
#   │    :5173       │     :5174      │
#   └────────────────┴────────────────┘

set -euo pipefail

SESSION="numina-dev"
SERVER_DIR="server"
MAIN_APP="frontend/apps/main"
CHILD_APP="frontend/apps/child"
PORTS=(8000 8001 8002 5173 5174)

# ── parameter parsing ────────────────────────────────────────────────
# Accept both env vars (MODE=, LOG=, DB=, CACHE=) and positional args.
# Env vars take precedence.

MODE="${DEV_MODE:-${MODE:-}}"
LOG="${DEV_LOG:-${LOG:-0}}"
DB="${DEV_DB:-${DB:-sqlite}}"
CACHE="${DEV_CACHE:-${CACHE:-memory}}"

case "${1:-}" in
    tmux|term|bg) MODE="${1}" ;;
esac
case "${2:-}" in
    0|1) LOG="${2}" ;;
esac

# Default mode: tmux if available, else term, else bg
if [ -z "$MODE" ]; then
    if command -v tmux >/dev/null 2>&1; then
        MODE="tmux"
    elif command -v osascript >/dev/null 2>&1 || command -v gnome-terminal >/dev/null 2>&1; then
        MODE="term"
    else
        MODE="bg"
    fi
fi

# Validate
case "$MODE" in
    tmux|term|bg) ;;
    *) echo "✗ 未知 MODE: $MODE (可选: tmux | term | bg)"; exit 1 ;;
esac
case "$LOG" in
    0|1) ;;
    *) echo "✗ 未知 LOG: $LOG (可选: 0 | 1)"; exit 1 ;;
esac
case "$DB" in
    sqlite|pgsql) ;;
    *) echo "✗ 未知 DB: $DB (可选: sqlite | pgsql)"; exit 1 ;;
esac
case "$CACHE" in
    memory|redis) ;;
    *) echo "✗ 未知 CACHE: $CACHE (可选: memory | redis)"; exit 1 ;;
esac

# ── log directory setup ──────────────────────────────────────────────

LOG_DIR_ABS=""
if [ "$LOG" = "1" ]; then
    LOG_DIR_ABS="$(cd "$SERVER_DIR" && pwd)/.dev-logs"
    mkdir -p "$LOG_DIR_ABS"
fi

# Build the DEV_LOG_DIR env value for Python services.
# "0" → console only; path → file logging; unset → default behavior.
if [ "$LOG" = "1" ]; then
    DEV_LOG_DIR_VALUE="$LOG_DIR_ABS"
else
    DEV_LOG_DIR_VALUE="0"
fi

# ── helpers ──────────────────────────────────────────────────────────

check_deps() {
    echo "检查并同步依赖..."
    make -s install
}

check_ports() {
    local occupied=0
    for port in "${PORTS[@]}"; do
        if lsof -iTCP:"$port" -sTCP:LISTEN -P -n >/dev/null 2>&1; then
            echo "✗ 端口 $port 已被占用:"
            lsof -iTCP:"$port" -sTCP:LISTEN -P -n 2>/dev/null | grep LISTEN || true
            occupied=1
        fi
    done
    if [ "$occupied" -eq 1 ]; then
        echo "请先运行 make stop-dev-all 释放端口"
        return 1
    fi
    return 0
}

# Python command prefix with DEV_LOG_DIR for file logging
py_env_prefix() {
    echo "DEV_LOG_DIR=$DEV_LOG_DIR_VALUE"
}

log_info() {
    if [ "$LOG" = "1" ]; then
        echo "  📝 Python 日志 → $LOG_DIR_ABS/{backend,agent,worker}.log"
    fi
}

# ── tmux mode ────────────────────────────────────────────────────────

launch_tmux() {
    # ── If already inside tmux, create a new window (not a nested session) ──
    local target window_flag=""
    if [ -n "${TMUX:-}" ]; then
        local cur_session
        cur_session="$(tmux display-message -p '#{session_name}')"
        target="$cur_session"
        echo "在当前 tmux session '$cur_session' 中创建新 window..."
    else
        if tmux has-session -t "$SESSION" 2>/dev/null; then
            echo "  session 已存在，连接中..."
            exec tmux attach-session -t "$SESSION"
        fi
        tmux new-session -d -s "$SESSION" -x "$(tput cols)" -y "$(tput lines)"
        target="$SESSION"
        echo "启动 tmux session '$SESSION' (上三下二布局)..."
    fi

    # Create window (inside existing session) or use initial window
    if [ -n "${TMUX:-}" ]; then
        tmux new-window -t "$target" -n "numina-dev"
        window_flag=1
    fi

    local server_dir main_dir child_dir
    server_dir="$(cd "$SERVER_DIR" && pwd)"
    main_dir="$(cd "$MAIN_APP" && pwd)"
    child_dir="$(cd "$CHILD_APP" && pwd)"

    local base
    base="$(tmux list-panes -t "$target" -F '#{pane_id}' | head -1)"

    # ── Split: 上三下二 (top 3, bottom 2) ────────────────────────────

    # Step 1: split vertically → top 60% / bottom 40%
    tmux split-window -v -l "60%" -t "$base"

    # Step 2: split top (-h) into 3 columns
    tmux split-window -h -l "67%" -t "$base"
    tmux split-window -h -l "50%" -t "$(tmux list-panes -t "$target" -F '#{pane_id} #{pane_left}' | sort -k2 -n | tail -1 | awk '{print $1}')"

    # Step 3: split bottom (-h) into 2 equal columns
    tmux split-window -h -l "50%" -t "$(tmux list-panes -t "$target" -F '#{pane_id} #{pane_top}' | sort -k2 -n | tail -1 | awk '{print $1}')"

    # Session / window options
    local tw="$target"
    [ -n "${TMUX:-}" ] && tw="$target:$(tmux display-message -p '#{window_index}')"
    tmux set-option -t "$tw" remain-on-exit on
    tmux set-option -t "$tw" mouse on
    tmux set-option -t "$tw" pane-border-status top
    tmux set-option -t "$tw" pane-border-format \
        '#{?pane_active,#[fg=green bold]#{pane_title},#[fg=default]#{pane_title}}'

    # ── Send commands to each pane (position-based) ──────────────────
    local pane_info
    pane_info="$(tmux list-panes -t "$target" -F '#{pane_id} #{pane_left} #{pane_top}')"

    local p_backend; p_backend="$(echo "$pane_info" | sort -k3,3n -k2,2n | head -1 | awk '{print $1}')"
    local p_worker; p_worker="$(echo "$pane_info" | sort -k3,3n -k2,2nr | head -1 | awk '{print $1}')"
    local p_agent; p_agent="$(echo "$pane_info" | sort -k3,3n -k2,2n | sed -n '2p' | awk '{print $1}')"
    local p_frontend; p_frontend="$(echo "$pane_info" | sort -k3,3nr -k2,2n | head -1 | awk '{print $1}')"
    local p_child; p_child="$(echo "$pane_info" | sort -k3,3nr -k2,2nr | head -1 | awk '{print $1}')"

    # Top-left — backend :8000
    tmux select-pane -t "$p_backend" -T "backend :8000"
    tmux send-keys -t "$p_backend" \
        "echo '═══ backend :8000 ═══'" Enter \
        "cd '$server_dir' && $(py_env_prefix) uv run uvicorn apps.backend.app.main:app --host 0.0.0.0 --reload --port 8000" Enter

    # Top-center — agent :8001
    tmux select-pane -t "$p_agent" -T "agent :8001"
    tmux send-keys -t "$p_agent" \
        "echo '═══ agent :8001 ═══'" Enter \
        "cd '$server_dir' && $(py_env_prefix) uv run uvicorn apps.agent.app.main:app --host 0.0.0.0 --reload --port 8001" Enter

    # Top-right — worker :8002
    tmux select-pane -t "$p_worker" -T "worker :8002"
    tmux send-keys -t "$p_worker" \
        "echo '═══ worker :8002 ═══'" Enter \
        "cd '$server_dir' && $(py_env_prefix) uv run uvicorn apps.scheduler_worker.main:app --host 0.0.0.0 --reload --port 8002" Enter

    # Bottom-left — frontend :5173
    tmux select-pane -t "$p_frontend" -T "frontend :5173"
    tmux send-keys -t "$p_frontend" \
        "echo '═══ frontend :5173 ═══'" Enter \
        "cd '$main_dir' && pnpm dev --host 0.0.0.0" Enter

    # Bottom-right — child :5174
    tmux select-pane -t "$p_child" -T "child :5174"
    tmux send-keys -t "$p_child" \
        "echo '═══ child :5174 ═══'" Enter \
        "cd '$child_dir' && pnpm dev --host 0.0.0.0" Enter

    # Select backend pane (top-left)
    tmux select-pane -t "$p_backend"

    # ── Attach / keep-alive ─────────────────────────────────────────
    if [ -n "${TMUX:-}" ]; then
        tmux select-window -t "$tw"
        echo "[numina-dev] 在 tmux window 中运行。"
        echo "  停止: make stop-dev-all"
        log_info
    else
        exec tmux attach-session -t "$SESSION"
    fi
}

# ── multi-terminal fallback ──────────────────────────────────────────

run_in_terminal() {
    local name="$1" port="$2" dir="$3" cmd="$4"

    case "$(uname -s)" in
        Darwin)
            local workdir="$dir"
            [ -d "$workdir" ] || workdir="$HOME"
            osascript -e "
                tell application \"Terminal\"
                    activate
                    set w to do script \"cd '$workdir' && echo '═══ $name :$port ═══' && $cmd\"
                    set custom title of w to \"$name\"
                end tell
            " >/dev/null 2>&1
            ;;
        Linux)
            if command -v gnome-terminal >/dev/null 2>&1; then
                gnome-terminal --title="$name" --working-directory="$dir" \
                    -- bash -c "echo '═══ $name :$port ═══'; $cmd" >/dev/null 2>&1
            elif command -v xterm >/dev/null 2>&1; then
                xterm -T "$name" -e "bash -c \"echo '═══ $name :$port ═══'; $cmd\"" >/dev/null 2>&1 &
            else
                return 1
            fi
            ;;
        *)
            if command -v start >/dev/null 2>&1; then
                start "$name" bash -c "cd '$dir' && echo '═══ $name :$port ═══' && $cmd" >/dev/null 2>&1
            else
                return 1
            fi
            ;;
    esac
    return 0
}

launch_terminals() {
    echo "启动 5 个独立终端窗口 (MODE=term)..."

    local server_abs main_abs child_abs
    server_abs="$(cd "$SERVER_DIR" && pwd)"
    main_abs="$(cd "$MAIN_APP" && pwd)"
    child_abs="$(cd "$CHILD_APP" && pwd)"

    local dev_log_env=""
    [ "$LOG" = "1" ] && dev_log_env="DEV_LOG_DIR=$DEV_LOG_DIR_VALUE "

    local services=(
        "backend|8000|$server_abs|${dev_log_env}uv run uvicorn apps.backend.app.main:app --host 0.0.0.0 --reload --port 8000"
        "agent|8001|$server_abs|${dev_log_env}uv run uvicorn apps.agent.app.main:app --host 0.0.0.0 --reload --port 8001"
        "worker|8002|$server_abs|${dev_log_env}uv run uvicorn apps.scheduler_worker.main:app --host 0.0.0.0 --reload --port 8002"
        "frontend|5173|$main_abs|pnpm dev --host 0.0.0.0"
        "child|5174|$child_abs|pnpm dev --host 0.0.0.0"
    )

    local ok=0
    for svc in "${services[@]}"; do
        IFS='|' read -r name port dir cmd <<< "$svc"
        if run_in_terminal "$name" "$port" "$dir" "$cmd"; then
            echo "  ✓ $name :$port"
            ok=$((ok + 1))
        else
            echo "  ✗ $name :$port — 无法打开终端"
        fi
    done

    echo ""
    echo "5 个服务已启动 (终端窗口)。"
    echo "  停止: make stop-dev-all"
    log_info
}

# ── background mode ──────────────────────────────────────────────────

launch_background() {
    echo "启动 5 个后台进程 (MODE=bg)..."

    local server_abs main_abs child_abs
    server_abs="$(cd "$SERVER_DIR" && pwd)"
    main_abs="$(cd "$MAIN_APP" && pwd)"
    child_abs="$(cd "$CHILD_APP" && pwd)"

    mkdir -p "$server_abs/.dev-logs"

    local services=(
        "backend|8000|$server_abs|uv run uvicorn apps.backend.app.main:app --host 0.0.0.0 --reload --port 8000"
        "agent|8001|$server_abs|uv run uvicorn apps.agent.app.main:app --host 0.0.0.0 --reload --port 8001"
        "worker|8002|$server_abs|uv run uvicorn apps.scheduler_worker.main:app --host 0.0.0.0 --reload --port 8002"
        "frontend|5173|$main_abs|pnpm dev --host 0.0.0.0"
        "child|5174|$child_abs|pnpm dev --host 0.0.0.0"
    )

    local pids=()
    for svc in "${services[@]}"; do
        IFS='|' read -r name port dir cmd <<< "$svc"
        local log_file="$server_abs/.dev-logs/$name.log"
        # Python services get DEV_LOG_DIR; frontend always stdout → file
        local env_prefix=""
        case "$name" in
            backend|agent|worker) env_prefix="DEV_LOG_DIR=$DEV_LOG_DIR_VALUE " ;;
        esac
        (cd "$dir" && eval "export $env_prefix && exec $cmd") >> "$log_file" 2>&1 &
        pids+=($!)
        echo "  ✓ $name :$port (PID $!) → $log_file"
    done

    echo ""
    echo "全部后台启动。查看日志:"
    if [ "$LOG" = "1" ]; then
        echo "  Python 服务日志 (via setup_logging): $LOG_DIR_ABS/{backend,agent,worker}.log"
        echo "  Shell stdout/stderr: $server_abs/.dev-logs/{backend,agent,worker,frontend,child}.log"
    else
        echo "  tail -f $server_abs/.dev-logs/{backend,agent,worker,frontend,child}.log"
    fi
    echo ""
    echo "停止: make stop-dev-all"

    # Trap SIGINT → kill all
    trap 'echo; echo "停止全部..."; kill "${pids[@]}" 2>/dev/null; wait 2>/dev/null; echo "✓ 已停止"' INT TERM
    wait
}

# ── main ─────────────────────────────────────────────────────────────

main() {
    echo "═══ Numina dev-all ═══"
    echo "  MODE=$MODE  LOG=$LOG  DB=$DB  CACHE=$CACHE"

    check_deps
    check_ports || exit 1

    # Apply .env overrides for DB and CACHE
    echo ""
    python3 scripts/dev/apply_dev_env.py --db "$DB" --cache "$CACHE" || exit 1
    echo ""

    case "$MODE" in
        tmux) launch_tmux ;;
        term) launch_terminals ;;
        bg)   launch_background ;;
    esac
}

main "$@"
