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

# Pull latest image (skip if using local image)
if [ -z "$RAGEX_IMAGE" ]; then
    echo "📦 Pulling latest image..."
    docker pull ghcr.io/jbenshetler/mcp-ragex:latest
else
    echo "📦 Using local image: $RAGEX_IMAGE"
fi

# Create user-specific data volume
USER_ID=$(id -u)
USER_VOLUME="ragex_user_${USER_ID}"
echo "💾 Creating user data volume: ${USER_VOLUME}..."
docker volume create "$USER_VOLUME"

# Create helper script
INSTALL_DIR="${HOME}/.local/bin"
mkdir -p "$INSTALL_DIR"

# Copy the smart wrapper scripts
echo "📝 Installing ragex wrappers..."

# Install main Python script as ragex
cp ragex "${INSTALL_DIR}/ragex"
chmod +x "${INSTALL_DIR}/ragex"

# Install MCP wrapper
cp ragex-mcp "${INSTALL_DIR}/ragex-mcp"
chmod +x "${INSTALL_DIR}/ragex-mcp"

# Also install bash script for testing
if [ -f "ragex.sh" ]; then
    echo "📝 Installing ragex.sh for testing..."
    cp ragex.sh "${INSTALL_DIR}/ragex.sh"
    chmod +x "${INSTALL_DIR}/ragex.sh"
fi

# Check if directory is in PATH
if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    echo ""
    echo "⚠️  Add $INSTALL_DIR to your PATH:"
    echo "   export PATH=\"\$PATH:$INSTALL_DIR\""
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "🔧 Your user data volume: ${USER_VOLUME}"
echo ""
echo "Quick start:"
echo "  1. cd your-project"
echo "  2. ragex index .                    # Index current project"
echo "  3. ragex info                       # Show project info"
echo "  4. ragex ls                         # List all your projects"
echo ""
echo "📝 Register with Claude Code:"
echo "  claude mcp add ragex $(which ragex-mcp 2>/dev/null || echo "${INSTALL_DIR}/ragex-mcp") --scope project"
echo ""
echo "For more info: https://github.com/jbenshetler/mcp-ragex"