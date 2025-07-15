#!/bin/bash
# Simple script to run the MCP code search server

# Check if ripgrep is installed
if ! command -v rg &> /dev/null; then
    echo "Error: ripgrep (rg) is not installed."
    echo "Please install it first:"
    echo "  macOS: brew install ripgrep"
    echo "  Ubuntu: sudo apt-get install ripgrep"
    echo "  Windows: choco install ripgrep"
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed."
    exit 1
fi

# Get the directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Run the server
echo "Starting CodeRAG MCP Server..."
echo "Using ripgrep: $(which rg)"
echo "Working directory: $(pwd)"
echo ""

cd "$DIR"

# Check if uv is available and use it, otherwise fall back to python3
if command -v uv &> /dev/null; then
    echo "Using uv to run the server..."
    uv run python src/server.py
else
    echo "Using python3 directly..."
    python3 src/server.py
fi