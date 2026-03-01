#!/bin/bash
# .github/hooks/setup.sh
# Runs at session start — ensures all dependencies are installed
# before the agent attempts any tasks.
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

echo "🔧 aigile session setup..."

# ── Backend ────────────────────────────────────────────────────────────────
BACKEND="$REPO_ROOT/backend"
if [ -f "$BACKEND/requirements.txt" ]; then
  echo "  → Installing Python dependencies..."
  pip install -r "$BACKEND/requirements.txt" --quiet --disable-pip-version-check
  echo "  ✅ Backend dependencies ready"
fi

# ── Frontend ───────────────────────────────────────────────────────────────
FRONTEND="$REPO_ROOT/frontend"
if [ -f "$FRONTEND/package.json" ]; then
  if [ ! -d "$FRONTEND/node_modules" ]; then
    echo "  → Installing Node dependencies (first time)..."
    cd "$FRONTEND" && npm install --silent
    echo "  ✅ Frontend dependencies installed"
  else
    echo "  → Syncing Node dependencies..."
    cd "$FRONTEND" && npm install --silent
    echo "  ✅ Frontend dependencies synced"
  fi
fi

echo "✅ Setup complete — agent is ready"
