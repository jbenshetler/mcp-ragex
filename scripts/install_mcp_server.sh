#!/bin/bash
# Install MCP server with all dependencies in its own environment

set -e

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Installing MCP RAGex Server..."
echo "Project root: $PROJECT_ROOT"

# Change to project root
cd "$PROJECT_ROOT"

# Create a dedicated venv for the MCP server if it doesn't exist
if [ ! -d ".mcp_venv" ]; then
    echo "Creating dedicated MCP server virtual environment..."
    uv venv .mcp_venv
fi

# Install all dependencies in the MCP venv
echo "Installing dependencies..."
uv pip install --python .mcp_venv/bin/python -r requirements.txt

# Install semantic search dependencies
echo "Installing semantic search dependencies..."
uv pip install --python .mcp_venv/bin/python \
    numpy \
    sentence-transformers \
    chromadb \
    torch

echo ""
echo "✅ MCP server installation complete!"
echo ""
echo "The MCP server now has its own isolated environment with all dependencies."
echo "This ensures consistent behavior across all projects."
echo ""
echo "Next steps:"
echo "1. Update your MCP registration to use the new wrapper script:"
echo "   claude mcp add ragex $PROJECT_ROOT/mcp_server_isolated.sh --scope project"
echo ""