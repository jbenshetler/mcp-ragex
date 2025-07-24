#!/bin/bash
# entrypoint.sh
set -e

# Function to check if workspace is mounted
check_workspace() {
    if [ ! -d "/workspace" ] || [ -z "$(ls -A /workspace 2>/dev/null)" ]; then
        echo "❌ Error: No workspace mounted. Mount your project directory to /workspace"
        echo "   Example: docker run -v \$(pwd):/workspace:ro ..."
        exit 1
    fi
}

# Handle different commands
case "$1" in
    "index")
        check_workspace
        shift
        exec python scripts/build_semantic_index.py "$@"
        ;;
    "serve"|"server")
        exec python -m src.server
        ;;
    "search")
        shift
        exec python ragex_search.py "$@"
        ;;
    "bash"|"sh")
        exec "$@"
        ;;
    *)
        # Default to MCP server
        exec python -m src.server "$@"
        ;;
esac