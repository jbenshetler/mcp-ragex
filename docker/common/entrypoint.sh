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

# Check if we're running inside the daemon (docker exec)
is_daemon_exec() {
    # If RAGEX_DAEMON_INITIALIZED is set, we're in a docker exec
    [ -n "${RAGEX_DAEMON_INITIALIZED}" ]
}

# Function to setup project-specific data directories
setup_project_data() {
    # Skip if already initialized (running via docker exec in daemon)
    if is_daemon_exec; then
        return 0
    fi
    # Generate project identifier from workspace path (if available) or use default
    if [ -d "/workspace" ] && [ -n "$(ls -A /workspace 2>/dev/null)" ]; then
        # Use hash for unique project ID (directory name)
        # Must match Python's generate_project_id() calculation: f"{user_id}:{abs_path}"
        PROJECT_HASH=$(echo -n "$(id -u):${WORKSPACE_PATH}" | sha256sum | cut -d' ' -f1 | head -c 16)
        PROJECT_ID="ragex_$(id -u)_${PROJECT_HASH}"
        
        # Check if custom name provided via environment, otherwise use workspace basename
        if [ -n "$RAGEX_PROJECT_NAME" ]; then
            PROJECT_NAME="$RAGEX_PROJECT_NAME"
        else
            PROJECT_NAME="$(basename "$WORKSPACE_PATH")"
        fi
    else
        PROJECT_ID=".ragex_admin"
        PROJECT_NAME=".ragex_admin"
    fi
    
    # Set up project-specific directories using PROJECT_ID
    export RAGEX_PROJECT_DATA_DIR="/data/projects/${PROJECT_ID}"
    export RAGEX_CHROMA_PERSIST_DIR="${RAGEX_PROJECT_DATA_DIR}/chroma_db"
    export RAGEX_CHROMA_COLLECTION="${RAGEX_CHROMA_COLLECTION:-code_embeddings}"
    
    # Models remain shared across projects for efficiency
    export HF_HOME="/data/models"
    export SENTENCE_TRANSFORMERS_HOME="/data/models"
    
    # Create project directories if they don't exist
    mkdir -p "${RAGEX_PROJECT_DATA_DIR}"
    mkdir -p "${RAGEX_CHROMA_PERSIST_DIR}"
    mkdir -p "/data/models"
    
    # Note: Project metadata (project_info.json) is now managed entirely by smart_index.py
    # This ensures proper handling of --name parameter and other project-specific logic
    
    # Only show project info for non-search commands or if log level is INFO or DEBUG
    if [[ ! "$1" =~ ^search ]] || [[ "${RAGEX_LOG_LEVEL^^}" == "INFO" ]] || [[ "${RAGEX_LOG_LEVEL^^}" == "DEBUG" ]]; then
        echo "📊 Data dir: ${RAGEX_PROJECT_DATA_DIR}"
        echo "🔧 Embedding model: ${RAGEX_EMBEDDING_MODEL:-fast}"
    fi
}

# Handle different commands
case "$1" in
    "index")
        setup_project_data "$@"
        check_workspace
        shift
        # Pass the workspace directory and ensure correct persist dir
        export RAGEX_INDEX_PATH="/workspace"
        # .mcpignore warnings are suppressed by default in Dockerfile
        # Pass user ID for project detection
        export DOCKER_USER_ID="${DOCKER_USER_ID}"
        
        # Use smart_index.py which handles checksums and project detection
        exec python scripts/smart_index.py "$@"
        ;;
    "serve")
        setup_project_data "$@"
        exec python -m src.server
        ;;
    "search")
        setup_project_data "$@"
        shift
        export RAGEX_CHROMA_PERSIST_DIR="${RAGEX_PROJECT_DATA_DIR}/chroma_db"
        # .mcpignore warnings are suppressed by default in Dockerfile
        # Disable logging setup override
        export RAGEX_DISABLE_LOGGING_SETUP=true
        exec python ragex_search.py --index-dir "${RAGEX_PROJECT_DATA_DIR}" "$@"
        ;;
    "ls")
        # Use Python handler for ls command
        shift
        exec python -m src.admin_cli ls "$@"
        ;;
    "rm")
        # Use Python handler for rm command
        shift
        exec python -m src.admin_cli rm "$@"
        ;;
    "register")
        # Use Python handler for register command
        shift
        exec python -m src.admin_cli register "$@"
        ;;
    "unregister")
        # Use Python handler for unregister command
        shift
        exec python -m src.admin_cli unregister "$@"
        ;;
    "info")
        setup_project_data "$@"
        # Show project info without needing workspace
        if [ -f "${RAGEX_PROJECT_DATA_DIR}/project_info.json" ]; then
            echo "📊 Project Information:"
            cat "${RAGEX_PROJECT_DATA_DIR}/project_info.json" | jq .
            
            # Check if ChromaDB exists and has data
            if [ -d "${RAGEX_CHROMA_PERSIST_DIR}" ]; then
                echo ""
                echo "📈 Index Statistics:"
                python -c "
from src.ragex_core.vector_store import CodeVectorStore
from src.ragex_core.embedding_manager import EmbeddingManager
try:
    em = EmbeddingManager()
    vs = CodeVectorStore()
    stats = vs.get_stats()
    print(f'  Total symbols: {stats[\"total_symbols\"]}')
    print(f'  Unique files: {stats[\"unique_files\"]}')
    if stats['languages']:
        print(f'  Languages: {\", \".join(stats[\"languages\"].keys())}')
    if stats['types']:
        print(f'  Symbol types: {\", \".join(stats[\"types\"].keys())}')
except Exception as e:
    print(f'  Error reading stats: {e}')
"
            else
                echo "❌ No index found. Run 'ragex index .' to create one."
            fi
        else
            echo "❌ No project data found. Run 'ragex init' first."
        fi
        ;;
    "search-symbol"|"search-regex")
        setup_project_data "$@"
        shift
        export RAGEX_CHROMA_PERSIST_DIR="${RAGEX_PROJECT_DATA_DIR}/chroma_db"
        # .mcpignore warnings are suppressed by default in Dockerfile
        # Disable logging setup override
        export RAGEX_DISABLE_LOGGING_SETUP=true
        exec python ragex_search.py --index-dir "${RAGEX_PROJECT_DATA_DIR}" "$@"
        ;;
    "daemon")
        # Long-running daemon mode with socket server for fast command execution
        setup_project_data "$@"
        export PYTHONPATH=/app:$PYTHONPATH
        export RAGEX_DAEMON_INITIALIZED=1
        
        # Change to workspace directory so commands run in the correct context
        cd /workspace
        
        echo "🚀 Starting RageX socket daemon..."
        echo "📊 Project: ${PROJECT_NAME}"
        echo "💾 Data dir: ${RAGEX_PROJECT_DATA_DIR}"
        echo "📁 Working directory: $(pwd)"
        
        # Start the socket daemon
        # Run socket daemon and if it fails, show error and exit
        python -m src.socket_daemon || {
            echo "❌ Socket daemon failed to start"
            exit 1
        }
        ;;
    "mcp"|"--mcp")
        # MCP mode - absolute silence required but need working directory
        # Set MCP_WORKING_DIR without printing anything
        export MCP_WORKING_DIR="/workspace"
        
        # Just run the MCP server with startup errors logged
        exec python -m src.server "$@" 2>/tmp/ragex-mcp-startup.log
        ;;
    *)
        # Unknown command
        echo "❌ Error: Unknown command '$1'"
        echo ""
        echo "Available commands:"
        echo "  index [PATH]       Build semantic index"
        echo "  search QUERY       Search in project"
        echo "  info               Show project information"
        echo "  ls                 List all projects"
        echo "  rm ID              Remove project data"
        echo "  register           Show registration instructions"
        echo "  unregister         Show unregistration instructions"
        echo "  --mcp              Run MCP server (JSON protocol only)"
        exit 1
        ;;
esac