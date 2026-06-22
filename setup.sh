#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "============================================"
echo " MCP Workflow Proxy -- Setup (Mac/Linux)"
echo "============================================"
echo ""

# Check Python is available
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found. Install Python 3.10+ first."
    echo "Mac:   brew install python"
    echo "Linux: sudo apt install python3 python3-venv"
    exit 1
fi

echo "[1/3] Creating virtual environment..."
python3 -m venv "$SCRIPT_DIR/venv"

echo "[2/3] Installing dependencies..."
"$SCRIPT_DIR/venv/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" --quiet

echo "[3/3] Generating Claude Desktop config snippet..."
"$SCRIPT_DIR/venv/bin/python" "$SCRIPT_DIR/generate_config.py"

echo ""
echo "============================================"
echo " Done! Follow the steps above to finish."
echo "============================================"
