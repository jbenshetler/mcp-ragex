#!/bin/bash
# install.sh
set -e

echo "🚀 Installing MCP-RageX Server..."

# Default to CPU, allow explicit override
MODE="cpu"  # Default

# Parse optional flags
while [[ $# -gt 0 ]]; do
    case $1 in
        --cpu) MODE="cpu"; shift ;;
        --cuda) MODE="cuda"; shift ;;
        --rocm) MODE="rocm"; shift ;;  # Future
        *) echo "❌ Unknown option: $1"; echo "Valid options: --cpu, --cuda"; exit 1 ;;
    esac
done

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

# Show what we're installing and set image tag
if [[ "$MODE" == "cuda" ]]; then
    echo "🚀 Installing CUDA version (~8GB download)..."
    IMAGE_TAG="cuda-latest"
elif [[ "$MODE" == "rocm" ]]; then
    echo "🚀 Installing ROCm version (~8GB download)..."
    IMAGE_TAG="rocm-latest"
else
    echo "🚀 Installing CPU version (~2GB download)..."
    IMAGE_TAG="cpu-latest"
fi

# Check for RAGEX_IMAGE override (for local development)
if [ -n "$RAGEX_IMAGE" ]; then
    echo "📦 Using local image override: $RAGEX_IMAGE"
    DOCKER_IMAGE="$RAGEX_IMAGE"
else
    DOCKER_IMAGE="ghcr.io/jbenshetler/mcp-ragex:$IMAGE_TAG"
    echo "📦 Pulling image: $DOCKER_IMAGE"
    docker pull "$DOCKER_IMAGE"
fi

# Stop and remove any existing ragex daemon containers
echo "🧹 Stopping and removing any existing ragex daemon containers..."
docker ps -a -q -f "name=ragex_daemon_" | xargs -r docker stop 2>/dev/null || true
docker ps -a -q -f "name=ragex_daemon_" | xargs -r docker rm 2>/dev/null || true

# Create user-specific data volume
USER_ID=$(id -u)
USER_VOLUME="ragex_user_${USER_ID}"
echo "💾 Creating user data volume: ${USER_VOLUME}..."
docker volume create "$USER_VOLUME"

# Create helper script
INSTALL_DIR="${HOME}/.local/bin"
mkdir -p "$INSTALL_DIR"

# Create config directory (XDG-compliant)
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/ragex"
CONFIG_FILE="$CONFIG_DIR/config.json"
mkdir -p "$CONFIG_DIR"

# Always overwrite config during installation (user's explicit choice)
cat > "$CONFIG_FILE" <<EOF
{
    "docker_image": "$DOCKER_IMAGE",
    "mode": "$MODE",
    "installed_at": "$(date -Iseconds)"
}
EOF

echo "✅ Configuration saved: $CONFIG_FILE (mode: $MODE)"

# Copy the smart wrapper scripts
echo "📝 Installing ragex wrappers..."

# Install main Python script as ragex
cp ragex "${INSTALL_DIR}/ragex"
chmod +x "${INSTALL_DIR}/ragex"

# Install MCP wrapper
cp ragex-mcp "${INSTALL_DIR}/ragex-mcp"
chmod +x "${INSTALL_DIR}/ragex-mcp"


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
echo "💡 Configuration:"
echo "  ragex configure                     # Show current config"
echo "  ragex configure --cpu               # Switch to CPU mode"
echo "  ragex configure --cuda              # Switch to CUDA mode"
echo ""
echo "📝 Register with Claude Code:"
echo "  claude mcp add ragex $(which ragex-mcp 2>/dev/null || echo "${INSTALL_DIR}/ragex-mcp") --scope project"
echo ""
echo "For more info: https://github.com/jbenshetler/mcp-ragex"