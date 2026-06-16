#!/bin/bash
# restart-ai-chat-all.sh
#
# Restart all services required for AI chat testing:
#   - Backend (port 8000)
#   - Agent (port 8001)
#   - Frontend main app (port 5173)
#
# Usage: ./scripts/dev/restart-ai-chat-all.sh [--skip-backend] [--skip-agent] [--skip-frontend]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SERVER_DIR="$PROJECT_ROOT/server"
FRONTEND_DIR="$PROJECT_ROOT/frontend/apps/main"

# Parse arguments
SKIP_BACKEND=false
SKIP_AGENT=false
SKIP_FRONTEND=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --skip-backend)  SKIP_BACKEND=true; shift ;;
    --skip-agent)    SKIP_AGENT=true; shift ;;
    --skip-frontend) SKIP_FRONTEND=true; shift ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

echo "🔄 Restarting AI chat services..."
echo "   Project root: $PROJECT_ROOT"

# Function to kill process on port
kill_port() {
  local port=$1
  local service_name=$2
  local pid=$(lsof -ti:$port 2>/dev/null || true)
  if [ -n "$pid" ]; then
    echo "   🛑 Stopping $service_name (PID: $pid, Port: $port)"
    kill $pid 2>/dev/null || true
    sleep 1
  fi
}

# Backend
if [ "$SKIP_BACKEND" = false ]; then
  echo ""
  echo "📦 Backend (uvicorn, port 8000)"
  kill_port 8000 "backend"

  cd "$SERVER_DIR"
  echo "   🚀 Starting backend..."
  uv run uvicorn apps.backend.app.main:app --host 0.0.0.0 --reload --port 8000 &
  BACKEND_PID=$!
  echo "   ✅ Backend started (PID: $BACKEND_PID)"
fi

# Agent
if [ "$SKIP_AGENT" = false ]; then
  echo ""
  echo "🤖 Agent (uvicorn, port 8001)"
  kill_port 8001 "agent"

  cd "$SERVER_DIR"
  echo "   🚀 Starting agent..."
  # Agent requires environment variables
  # These should be set in .env or passed explicitly
  uv run uvicorn apps.agent.app.main:app --host 0.0.0.0 --reload --port 8001 &
  AGENT_PID=$!
  echo "   ✅ Agent started (PID: $AGENT_PID)"
fi

# Frontend
if [ "$SKIP_FRONTEND" = false ]; then
  echo ""
  echo "🎨 Frontend main app (Vite, port 5173)"
  kill_port 5173 "frontend"

  cd "$FRONTEND_DIR"
  echo "   🚀 Starting frontend..."
  pnpm dev --host 0.0.0.0 &
  FRONTEND_PID=$!
  echo "   ✅ Frontend started (PID: $FRONTEND_PID)"
fi

echo ""
echo "✅ All services restarted!"
echo ""
echo "Services:"
if [ "$SKIP_BACKEND" = false ]; then  echo "   Backend:  http://localhost:8000"; fi
if [ "$SKIP_AGENT" = false ]; then    echo "   Agent:    http://localhost:8001"; fi
if [ "$SKIP_FRONTEND" = false ]; then echo "   Frontend: http://localhost:5173"; fi
echo ""
echo "AI Chat: http://localhost:5173/ai/chat"
echo ""
echo "Press Ctrl+C to stop all services (or kill individual PIDs)"

# Wait for all background processes
wait