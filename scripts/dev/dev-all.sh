#!/usr/bin/env bash
# scripts/dev/dev-all.sh — Launch all Numina dev servers with split-pane logs
#
# Priority:
#   1. tmux  → single session, 5 panes in 3+2 layout
#   2. GUI terminal (macOS Terminal/iTerm2, Linux x-terminal-emulator)
#              → 5 separate terminal windows
#   3. Background + log files (last resort, no live view)
#
# Layout (tmux):
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
    echo "启动 tmux session '$SESSION' (3+2 布局)..."

    # Already exists → reattach / switch
    if tmux has-session -t "$SESSION" 2>/dev/null; then
        echo "  session 已存在，连接中..."
        if [ -n "${TMUX:-}" ]; then
            tmux switch-client -t "$SESSION"
        else
            exec tmux attach-session -t "$SESSION"
        fi
        return
    fi

    local server_dir
    server_dir="$(cd "$SERVER_DIR" && pwd)"
    local main_dir child_dir
    main_dir="$(cd "$MAIN_APP" && pwd)"
    child_dir="$(cd "$CHILD_APP" && pwd)"

    # Create session (detached) — pane %base
    tmux new-session -d -s "$SESSION" -x "$(tput cols)" -y "$(tput lines)"
    local base
    base="$(tmux list-panes -t "$SESSION" -F '#{pane_id}' | head -1)"

    # ── Top row: 3 equal panes ──────────────────────────────────────
    tmux split-window -h -t "$base" -c "$server_dir"
    tmux split-window -h -t "$base" -c "$server_dir"
    # base → P3(left), P2(mid), P1(right)

    # ── Bottom row: split base vertically → 2 panes ─────────────────
    tmux split-window -v -t "$base" -l "60%" -c "$main_dir"
    tmux split-window -h -t "$base" -c "$child_dir"
    # base → P4(bottom-left), P5(bottom-right)

    # Session options
    tmux set-option -t "$SESSION" remain-on-exit on
    tmux set-option -t "$SESSION" mouse on
    tmux set-option -t "$SESSION" pane-border-status top
    tmux set-option -t "$SESSION" pane-border-format \
        '#{?pane_active,#[fg=green bold]#{pane_title},#[fg=default]#{pane_title}}'

    # ── Send commands to each pane ──────────────────────────────────
    # Pane creation order (by split sequence):
    #   Pane 4 (top-right)   = first created   → backend
    #   Pane 3 (top-center)  = second created   → agent
    #   Pane 0 (top-left)    = base (remainder)  → worker
    #   Pane 2 (bottom-left) = third created     → frontend
    #   Pane 1 (bottom-right)= fourth created    → child

    # Pane 4 (top-right) — backend :8000
    tmux select-pane -t "$SESSION:0.4" -T "backend :8000"
    tmux send-keys -t "$SESSION:0.4" \
        "echo '═══ backend :8000 ═══'" Enter \
        "uv run uvicorn apps.backend.app.main:app --host 0.0.0.0 --reload --port 8000" Enter

    # Pane 3 (top-center) — agent :8001
    tmux select-pane -t "$SESSION:0.3" -T "agent :8001"
    tmux send-keys -t "$SESSION:0.3" \
        "echo '═══ agent :8001 ═══'" Enter \
        "uv run uvicorn apps.agent.app.main:app --host 0.0.0.0 --reload --port 8001" Enter

    # Pane 0 (top-left) — worker :8002
    tmux select-pane -t "$SESSION:0.0" -T "worker :8002"
    tmux send-keys -t "$SESSION:0.0" \
        "echo '═══ worker :8002 ═══'" Enter \
        "uv run uvicorn apps.scheduler_worker.main:app --host 0.0.0.0 --reload --port 8002" Enter

    # Pane 2 (bottom-left) — frontend :5173
    tmux select-pane -t "$SESSION:0.2" -T "frontend :5173"
    tmux send-keys -t "$SESSION:0.2" \
        "echo '═══ frontend :5173 ═══'" Enter \
        "pnpm dev --host 0.0.0.0" Enter

    # Pane 1 (bottom-right) — child :5174
    tmux select-pane -t "$SESSION:0.1" -T "child :5174"
    tmux send-keys -t "$SESSION:0.1" \
        "echo '═══ child :5174 ═══'" Enter \
        "pnpm dev --host 0.0.0.0" Enter

    # Select backend pane (top-right)
    tmux select-pane -t "$SESSION:0.4"

    # Attach (foreground — Ctrl-C kills all services)
    if [ -n "${TMUX:-}" ]; then
        # Inside existing tmux → switch; keep script alive for trap
        tmux switch-client -t "$SESSION"
        trap 'tmux kill-session -t "$SESSION" 2>/dev/null || true' EXIT
        echo "[numina-dev] 在 tmux 中运行。Ctrl-D 退出或 :detach 分离。"
        echo "  另一个终端: make stop-dev-all 停止全部"
        wait
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
