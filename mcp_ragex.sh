#!/bin/bash
# MCP Server wrapper with robust dependency handling
# This script ensures dependencies are available while preserving stdio

# Save current directory
WORK_DIR="$(pwd)"

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Export working directory for the server
export MCP_WORKING_DIR="$WORK_DIR"

# Change to script directory
cd "$SCRIPT_DIR"

# Check if we should use isolated venv or uv
if [ -f "$SCRIPT_DIR/.mcp_venv/bin/python" ]; then
    # Use isolated MCP venv if it exists
    exec "$SCRIPT_DIR/.mcp_venv/bin/python" -u src/server.py
elif command -v uv >/dev/null 2>&1; then
    # Use uv if available
    exec uv run python -u src/server.py
else
    # Fallback to system python and hope for the best
    exec python3 -u src/server.py
fi