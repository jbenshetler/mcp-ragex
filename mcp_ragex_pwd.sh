#!/bin/bash
# MCP Server wrapper - runs from current working directory

# Save current directory
WORK_DIR="$(pwd)"

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Export working directory for the server to use
export MCP_WORKING_DIR="$WORK_DIR"

# Change to script directory to run with uv
cd "$SCRIPT_DIR"

# Run the server
exec uv run python src/server.py