#!/bin/bash
# install.sh
set -e

echo "🚀 Installing MCP-RageX Server..."

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    echo "   Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check Docker daemon
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker daemon not running. Please start Docker."
    exit 1
fi

# Pull latest image
echo "📦 Pulling latest image..."
docker pull ragex/mcp-server:latest

# Create volume for persistent data
echo "💾 Creating data volume..."
docker volume create ragex-data

# Create helper script
INSTALL_DIR="${HOME}/.local/bin"
mkdir -p "$INSTALL_DIR"

cat > "${INSTALL_DIR}/ragex" << 'EOF'
#!/bin/bash
# MCP-RageX CLI wrapper

# Default to current directory for workspace
WORKSPACE="${WORKSPACE:-$(pwd)}"

# Run Docker container
docker run -it --rm \
  -v "${WORKSPACE}:/workspace:ro" \
  -v "ragex-data:/data" \
  -e "RAGEX_LOG_LEVEL=${RAGEX_LOG_LEVEL:-INFO}" \
  ragex/mcp-server:latest "$@"
EOF

chmod +x "${INSTALL_DIR}/ragex"

# Check if directory is in PATH
if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    echo ""
    echo "⚠️  Add $INSTALL_DIR to your PATH:"
    echo "   export PATH=\"\$PATH:$INSTALL_DIR\""
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "Quick start:"
echo "  1. cd your-project"
echo "  2. ragex index ."
echo "  3. Configure Claude with MCP settings"
echo ""
echo "For more info: https://github.com/anthropics/mcp-ragex"