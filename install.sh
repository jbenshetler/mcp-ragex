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

# Copy the smart wrapper script
echo "📝 Installing ragex wrapper..."
cat > "${INSTALL_DIR}/ragex" << 'EOF'
#!/bin/bash
# MCP-RageX CLI wrapper with project isolation
set -e

# Show help if no arguments or --help
if [ $# -eq 0 ] || [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    cat << 'HELPEOF'
MCP-RageX - AI-powered code search server

Usage: ragex <command> [options]

Commands:
  init                 Initialize .mcpignore in current directory
  index <path>         Index a directory for semantic search
  info                 Show project information and statistics
  list-projects        List all indexed projects
  search <query>       Search indexed code (semantic search)
  search-symbol <name> Search for function/class names
  search-regex <pat>   Search using regular expressions
  bash                 Start interactive shell in container
  sh                   Start sh shell in container

Environment Variables:
  RAGEX_EMBEDDING_MODEL  Model to use: 'fast' (default) or 'accurate'

Examples:
  ragex init                    # Create .mcpignore file
  ragex index .                 # Index current directory
  ragex search "auth logic"     # Semantic search
  ragex search-symbol parseURL  # Find function/class
  ragex info                    # Show project stats

Register with Claude Code:
  claude mcp add ragex $(which ragex) --scope project

HELPEOF
    exit 0
fi

USER_ID=$(id -u)
GROUP_ID=$(id -g)
USER_VOLUME="ragex_user_${USER_ID}"
WORKSPACE_PATH="${PWD}"
PROJECT_HASH=$(echo "${USER_ID}:${WORKSPACE_PATH}" | sha256sum | cut -d' ' -f1 | head -c 16)
PROJECT_ID="ragex_${USER_ID}_${PROJECT_HASH}"

DOCKER_ARGS=(
    "run" "--rm"
    "-u" "${USER_ID}:${GROUP_ID}"
    "-v" "${USER_VOLUME}:/data"
)

# Mount workspace as read-write for init command, read-only for others
if [ "$1" = "init" ]; then
    DOCKER_ARGS+=("-v" "${WORKSPACE_PATH}:/workspace:rw")
else
    DOCKER_ARGS+=("-v" "${WORKSPACE_PATH}:/workspace:ro")
fi

DOCKER_ARGS+=(
    "-e" "WORKSPACE_PATH=${WORKSPACE_PATH}"
    "-e" "PROJECT_NAME=${PROJECT_ID}"
    "-e" "RAGEX_EMBEDDING_MODEL=${RAGEX_EMBEDDING_MODEL:-fast}"
)

if [ "$1" = "bash" ] || [ "$1" = "sh" ]; then
    DOCKER_ARGS+=("-it")
fi

exec docker "${DOCKER_ARGS[@]}" ${RAGEX_IMAGE:-ghcr.io/jbenshetler/mcp-ragex:latest} "$@"
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
echo "🔧 Your user data volume: ${USER_VOLUME}"
echo ""
echo "Quick start:"
echo "  1. cd your-project"
echo "  2. ragex index .                    # Index current project"
echo "  3. ragex info                       # Show project info"
echo "  4. ragex list-projects              # List all your projects"
echo ""
echo "📝 Register with Claude Code:"
echo "  claude mcp add ragex $(which ragex) --scope project"
echo ""
echo "For more info: https://github.com/jbenshetler/mcp-ragex"