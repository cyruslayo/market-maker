#!/bin/bash

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"

echo "------------------------------------------"
echo "🚀 Starting Market Maker Update"
echo "------------------------------------------"

cd "$PROJECT_DIR" || exit

# 1. Pull latest code
echo "📦 Pulling latest changes from Git..."
git pull origin main

# 2. Update dependencies
if [ -d "$VENV_DIR" ]; then
    echo "🐍 Updating Python dependencies..."
    source "$VENV_DIR/bin/activate"
    pip install -r requirements.txt
else
    echo "⚠️  Warning: Virtual environment (venv) not found at $VENV_DIR"
fi

# 3. Clean up (Optional - running the project's cleanup script)
if [ -f "polymarket-automated-mm/REMOVE_UNUSED_SCRIPTS.sh" ]; then
    echo "🧹 Cleaning up unused scripts..."
    bash polymarket-automated-mm/REMOVE_UNUSED_SCRIPTS.sh
fi

echo "------------------------------------------"
echo "✅ Update Complete!"
echo "------------------------------------------"
echo "Please restart your bot process if needed."
