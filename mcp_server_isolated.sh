#!/bin/bash
# MCP Server wrapper - uses dedicated MCP venv and runs from current working directory
# IMPORTANT: Uses exec to replace shell process and preserve stdio communication

# Save current directory (where Claude launched from - the project to search)
WORK_DIR="$(pwd)"

# Get script directory (where MCP server is installed)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Export working directory for the server to use
export MCP_WORKING_DIR="$WORK_DIR"

# Use the dedicated MCP venv Python directly
MCP_PYTHON="$SCRIPT_DIR/.mcp_venv/bin/python"

# Check if MCP venv exists
if [ ! -f "$MCP_PYTHON" ]; then
    echo "ERROR: MCP server not properly installed!" >&2
    echo "Please run: $SCRIPT_DIR/scripts/install_mcp_server.sh" >&2
    exit 1
fi

# Change to script directory (where server code is)
cd "$SCRIPT_DIR"

# CRITICAL: Use exec to replace the shell process entirely
# This ensures stdio is passed directly to Python without buffering
exec "$MCP_PYTHON" -u src/server.py