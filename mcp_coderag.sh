#!/bin/bash
# MCP Server wrapper script for CodeRAG
# This runs the server from the current working directory

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Run the server with uv from current directory (where Claude Code is working)
exec uv --directory "$SCRIPT_DIR" run python "$SCRIPT_DIR/src/server.py"