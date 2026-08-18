#!/usr/bin/env bash
# scripts/dev/dev-all.sh — Launch all Numina dev servers with split-pane logs
#
# Priority:
#   1. tmux  → single session, 5 panes in 3+2 layout
#   2. GUI terminal (macOS Terminal/iTerm2, Linux x-terminal-emulator)
#              → 5 separate terminal windows
#   3. Background + log files (last resort, no live view)
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

# ── helpers ──────────────────────────────────────────────────────────

check_deps() {
    # 服务端依赖：不存在则安装，lockfile/pyproject.toml 更新则同步
    if [ ! -d "$SERVER_DIR/.venv" ]; then
        echo ".venv 不存在，正在安装服务端依赖..."
        (cd "$SERVER_DIR" && uv sync --extra backend --extra agent --extra worker --all-groups)
        echo "✓ 服务端依赖安装完成"
    elif [ "$SERVER_DIR/uv.lock" -nt "$SERVER_DIR/.venv" ] || [ "$SERVER_DIR/pyproject.toml" -nt "$SERVER_DIR/.venv" ]; then
        echo "lockfile/pyproject.toml 已更新，正在同步服务端依赖..."
        (cd "$SERVER_DIR" && uv sync --extra backend --extra agent --extra worker --all-groups)
        echo "✓ 服务端依赖同步完成"
    fi
    # 前端依赖：不存在则安装，lockfile 更新则同步
    if [ ! -d "frontend/node_modules" ]; then
        echo "node_modules 不存在，正在安装前端依赖..."
        (cd frontend && pnpm install)
        echo "✓ 前端依赖安装完成"
    elif [ "frontend/pnpm-lock.yaml" -nt "frontend/node_modules" ]; then
        echo "pnpm-lock.yaml 已更新，正在同步前端依赖..."
        (cd frontend && pnpm install)
        echo "✓ 前端依赖同步完成"
    fi
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
    #   -l 67% → new right 67%, base keeps left 33%
    tmux split-window -h -l "67%" -t "$base"
    #   -l 50% of right → center 33.5%, right keeps 33.5%
    tmux split-window -h -l "50%" -t "$(tmux list-panes -t "$target" -F '#{pane_id} #{pane_left}' | sort -k2 -n | tail -1 | awk '{print $1}')"

    # Step 3: split bottom (-h) into 2 equal columns
    tmux split-window -h -l "50%" -t "$(tmux list-panes -t "$target" -F '#{pane_id} #{pane_top}' | sort -k2 -n | tail -1 | awk '{print $1}')"

    # ── Final layout ─────────────────────────────────────────────────
    #   ┌──────────┬──────────┬──────────┐
    #   │ backend  │  agent   │  worker  │
    #   │ p_left   │ p_center │ p_right  │
    #   ├───────────┴────┬─────┴──────────┤
    #   │   frontend     │     child      │
    #   │   p_bot        │     p_br       │
    #   └────────────────┴────────────────┘

    # Session / window options
    local tw="$target"
    [ -n "${TMUX:-}" ] && tw="$target:$(tmux display-message -p '#{window_index}')"
    tmux set-option -t "$tw" remain-on-exit on
    tmux set-option -t "$tw" mouse on
    tmux set-option -t "$tw" pane-border-status top
    tmux set-option -t "$tw" pane-border-format \
        '#{?pane_active,#[fg=green bold]#{pane_title},#[fg=default]#{pane_title}}'

    # ── Send commands to each pane (position-based) ──────────────────
    # Query pane positions and assign services by (left, top) coordinates.
    local pane_info
    pane_info="$(tmux list-panes -t "$target" -F '#{pane_id} #{pane_left} #{pane_top}')"

    # Top-left: min top, min left → backend
    local p_backend; p_backend="$(echo "$pane_info" | sort -k3,3n -k2,2n | head -1 | awk '{print $1}')"
    # Top-right: min top, max left → worker
    local p_worker; p_worker="$(echo "$pane_info" | sort -k3,3n -k2,2nr | head -1 | awk '{print $1}')"
    # Top-center: min top, middle left → agent
    local p_agent; p_agent="$(echo "$pane_info" | sort -k3,3n -k2,2n | sed -n '2p' | awk '{print $1}')"

    # Bottom-left: max top, min left → frontend
    local p_frontend; p_frontend="$(echo "$pane_info" | sort -k3,3nr -k2,2n | head -1 | awk '{print $1}')"
    # Bottom-right: max top, max left → child
    local p_child; p_child="$(echo "$pane_info" | sort -k3,3nr -k2,2nr | head -1 | awk '{print $1}')"

    # Top-left — backend :8000
    tmux select-pane -t "$p_backend" -T "backend :8000"
    tmux send-keys -t "$p_backend" \
        "echo '═══ backend :8000 ═══'" Enter \
        "cd '$server_dir' && uv run uvicorn apps.backend.app.main:app --host 0.0.0.0 --reload --port 8000" Enter

    # Top-center — agent :8001
    tmux select-pane -t "$p_agent" -T "agent :8001"
    tmux send-keys -t "$p_agent" \
        "echo '═══ agent :8001 ═══'" Enter \
        "cd '$server_dir' && uv run uvicorn apps.agent.app.main:app --host 0.0.0.0 --reload --port 8001" Enter

    # Top-right — worker :8002
    tmux select-pane -t "$p_worker" -T "worker :8002"
    tmux send-keys -t "$p_worker" \
        "echo '═══ worker :8002 ═══'" Enter \
        "cd '$server_dir' && uv run uvicorn apps.scheduler_worker.main:app --host 0.0.0.0 --reload --port 8002" Enter

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
    trap '
        if [ -n "${TMUX:-}" ] && [ -n "${window_flag:-}" ]; then
            tmux kill-window -t "'"$tw"'" 2>/dev/null || true
        else
            tmux kill-session -t "'"$SESSION"'" 2>/dev/null || true
        fi
    ' INT TERM

    if [ -n "${TMUX:-}" ]; then
        tmux select-window -t "$tw"
        echo "[numina-dev] 在 tmux window 中运行。"
        echo "  停止: make stop-dev-all"
        sleep 3600 & wait $!
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
            # Windows (Git Bash / MSYS) — try start
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
    echo "无 tmux，启动 5 个独立终端窗口..."

    local server_abs
    server_abs="$(cd "$SERVER_DIR" && pwd)"
    local main_abs child_abs
    main_abs="$(cd "$MAIN_APP" && pwd)"
    child_abs="$(cd "$CHILD_APP" && pwd)"

    local services=(
        "backend|8000|$server_abs|uv run uvicorn apps.backend.app.main:app --host 0.0.0.0 --reload --port 8000"
        "agent|8001|$server_abs|uv run uvicorn apps.agent.app.main:app --host 0.0.0.0 --reload --port 8001"
        "worker|8002|$server_abs|uv run uvicorn apps.scheduler_worker.main:app --host 0.0.0.0 --reload --port 8002"
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
}

# ── background fallback ─────────────────────────────────────────────

launch_background() {
    echo "无 tmux 且无法打开 GUI 终端，启动后台进程 (日志写入 server/.dev-logs/)..."
    mkdir -p "$SERVER_DIR/.dev-logs"

    local services=(
        "backend|8000|$SERVER_ABS|uv run uvicorn apps.backend.app.main:app --host 0.0.0.0 --reload --port 8000"
        "agent|8001|$SERVER_ABS|uv run uvicorn apps.agent.app.main:app --host 0.0.0.0 --reload --port 8001"
        "worker|8002|$SERVER_ABS|uv run uvicorn apps.scheduler_worker.main:app --host 0.0.0.0 --reload --port 8002"
        "frontend|5173|$MAIN_ABS|pnpm dev --host 0.0.0.0"
        "child|5174|$CHILD_ABS|pnpm dev --host 0.0.0.0"
    )

    local pids=()
    for svc in "${services[@]}"; do
        IFS='|' read -r name port dir cmd <<< "$svc"
        (cd "$dir" && exec $cmd) >> "$SERVER_DIR/.dev-logs/$name.log" 2>&1 &
        pids+=($!)
        echo "  ✓ $name :$port (PID $!) → $SERVER_DIR/.dev-logs/$name.log"
    done

    echo ""
    echo "全部后台启动。查看日志:"
    echo "  tail -f $SERVER_DIR/.dev-logs/{backend,agent,worker,frontend,child}.log"
    echo ""
    echo "停止: make stop-dev-all"

    # Trap SIGINT → kill all
    trap 'echo; echo "停止全部..."; kill "${pids[@]}" 2>/dev/null; wait 2>/dev/null; echo "✓ 已停止"' INT TERM
    wait
}

# ── main ─────────────────────────────────────────────────────────────

main() {
    check_deps
    check_ports || exit 1

    if command -v tmux >/dev/null 2>&1; then
        launch_tmux
    elif command -v osascript >/dev/null 2>&1 || command -v gnome-terminal >/dev/null 2>&1; then
        launch_terminals
    else
        # Pre-resolve absolute paths for background mode
        SERVER_ABS="$(cd "$SERVER_DIR" && pwd)"
        MAIN_ABS="$(cd "$MAIN_APP" && pwd)"
        CHILD_ABS="$(cd "$CHILD_APP" && pwd)"
        launch_background
    fi
}

main "$@"
