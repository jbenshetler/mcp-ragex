#!/bin/bash
# MCP Server wrapper script for RAGex
# This ensures the server runs with the correct working directory

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Change to the project directory
cd "$SCRIPT_DIR"

# Run the server with uv
exec uv run python src/server.py