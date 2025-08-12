#!/bin/bash
# install.sh
set -e

echo "🚀 Installing MCP-RAGex Server..."

# Default values
MODE=""  # Will be auto-detected if not specified
NETWORK_MODE="none"  # Default to secure (no network)
MODEL=""  # Will use 'fast' if not specified

# Parse optional flags
while [[ $# -gt 0 ]]; do
    case $1 in
        --cpu) MODE="cpu"; shift ;;
        --cuda) MODE="cuda"; shift ;;
        --rocm) MODE="rocm"; shift ;;  # Future
        --network) NETWORK_MODE="bridge"; shift ;;  # Enable network access
        --model) MODEL="$2"; shift 2 ;;  # Model parameter
        *) echo "❌ Unknown option: $1"; echo "Valid options: --cpu, --cuda, --network, --model <name>"; exit 1 ;;
    esac
done

# Auto-detect platform if not specified
if [[ -z "$MODE" ]]; then
    ARCH=$(uname -m)
    if [[ "$ARCH" == "x86_64" ]]; then
        if command -v nvidia-smi &> /dev/null && docker info | grep -q nvidia; then
            echo "🔍 Auto-detected: CUDA (NVIDIA GPU + Docker support found)"
            MODE="cuda"
        else
            echo "🔍 Auto-detected: AMD64 CPU"
            MODE="cpu"
        fi
    elif [[ "$ARCH" == "aarch64" ]] || [[ "$ARCH" == "arm64" ]]; then
        echo "🔍 Auto-detected: ARM64 CPU"
        MODE="cpu"
    else
        echo "❌ Unsupported architecture: $ARCH"
        echo "   Currently supported: AMD64, ARM64"
        exit 1
    fi
fi

# Validate model if specified
if [[ -n "$MODEL" ]]; then
    case "$MODEL" in
        fast|balanced|accurate|multilingual) ;;
        *) 
            echo "❌ Invalid model: $MODEL"
            echo "   Available models: fast, balanced, accurate, multilingual"
            exit 1
            ;;
    esac
fi

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
    echo "🚀 Installing CUDA version (~13GiB download)..."
    IMAGE_TAG="cuda-latest"
else
    echo "🚀 Installing CPU version (~3GiB download)..."
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
if [[ -n "$MODEL" ]]; then
    cat > "$CONFIG_FILE" <<EOF
{
    "docker_image": "$DOCKER_IMAGE",
    "mode": "$MODE",
    "network_mode": "$NETWORK_MODE",
    "default_embedding_model": "$MODEL",
    "installed_at": "$(date -Iseconds)"
}
EOF
else
    cat > "$CONFIG_FILE" <<EOF
{
    "docker_image": "$DOCKER_IMAGE",
    "mode": "$MODE",
    "network_mode": "$NETWORK_MODE",
    "installed_at": "$(date -Iseconds)"
}
EOF
fi

echo "✅ Configuration saved: $CONFIG_FILE (mode: $MODE)"

# Show security status to user
if [[ "$NETWORK_MODE" == "none" ]]; then
    echo "🔒 Installed in secure mode (no network access)"
    echo "   Only pre-bundled fast model will be available"
else
    echo "🌐 Installed with network access enabled" 
    echo "   All embedding models can be downloaded"
fi

# Extract and install the smart wrapper scripts from Docker image
echo "📝 Installing ragex wrappers..."

# Detect if we're running from repo (files exist) or remotely (need to extract from image)
if [[ -f "ragex" && -f "ragex-mcp" ]]; then
    echo "  📁 Using wrapper files from repository..."
    # Install main Python script as ragex
    cp ragex "${INSTALL_DIR}/ragex"
    chmod +x "${INSTALL_DIR}/ragex"
    # Install MCP wrapper
    cp ragex-mcp "${INSTALL_DIR}/ragex-mcp"
    chmod +x "${INSTALL_DIR}/ragex-mcp"
else
    echo "  📦 Extracting wrapper files from Docker image..."
    
    # Create temporary container to extract files
    TEMP_CONTAINER=$(docker create "$DOCKER_IMAGE")
    
    # Extract ragex wrapper from the repository root in the image
    docker cp "$TEMP_CONTAINER:/ragex" "${INSTALL_DIR}/ragex" 2>/dev/null || {
        echo "  ⚠️  ragex wrapper not found in image, creating fallback wrapper..."
        # Create a minimal fallback wrapper that uses the detected image
        cat > "${INSTALL_DIR}/ragex" << EOF
#!/bin/bash
# RAGex Docker wrapper (fallback)
# This is a simplified wrapper - consider cloning the repository for full functionality
exec docker run --rm -it \\
    -v "\$(pwd):/workspace:ro" \\
    -v "\$HOME/.config/ragex:/home/ragex/.config/ragex" \\
    -v "ragex_user_\$(id -u):/data" \\
    --user "\$(id -u):\$(id -g)" \\
    $DOCKER_IMAGE \\
    "\$@"
EOF
    }
    chmod +x "${INSTALL_DIR}/ragex"
    
    # Extract ragex-mcp wrapper
    docker cp "$TEMP_CONTAINER:/ragex-mcp" "${INSTALL_DIR}/ragex-mcp" 2>/dev/null || {
        echo "  ⚠️  ragex-mcp wrapper not found in image, creating fallback wrapper..."
        # Create simple MCP wrapper
        cat > "${INSTALL_DIR}/ragex-mcp" << 'EOF'
#!/bin/sh
# RAGex MCP wrapper (fallback)
exec "$(dirname "$0")/ragex" --mcp "$@"
EOF
    }
    chmod +x "${INSTALL_DIR}/ragex-mcp"
    
    # Cleanup temporary container
    docker rm "$TEMP_CONTAINER" >/dev/null
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
echo "💡 Configuration:"
echo "  ragex configure                     # Show current config"
echo "  ragex configure --cpu               # Switch to CPU mode"
echo "  ragex configure --cuda              # Switch to CUDA mode"
echo ""
echo "📝 Register with Claude Code:"
echo "  claude mcp add ragex $(which ragex-mcp 2>/dev/null || echo "${INSTALL_DIR}/ragex-mcp") --scope project"
echo ""
echo "For more info: https://github.com/jbenshetler/mcp-ragex"