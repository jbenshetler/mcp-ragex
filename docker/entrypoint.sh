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

# Function to setup project-specific data directories
setup_project_data() {
    # Generate project identifier from workspace path (if available) or use default
    if [ -d "/workspace" ] && [ -n "$(ls -A /workspace 2>/dev/null)" ]; then
        # Use a hash of the workspace path for consistent project identification
        PROJECT_HASH=$(echo "$WORKSPACE_PATH" | sha256sum | cut -d' ' -f1 | head -c 16)
        PROJECT_NAME="${PROJECT_NAME:-project_${PROJECT_HASH}}"
    else
        PROJECT_NAME="${PROJECT_NAME:-default_project}"
    fi
    
    # Set up project-specific directories
    export RAGEX_PROJECT_DATA_DIR="/data/projects/${PROJECT_NAME}"
    export RAGEX_CHROMA_PERSIST_DIR="${RAGEX_PROJECT_DATA_DIR}/chroma_db"
    export RAGEX_CHROMA_COLLECTION="${RAGEX_CHROMA_COLLECTION:-code_embeddings}"
    
    # Models remain shared across projects for efficiency
    export HF_HOME="/data/models"
    export SENTENCE_TRANSFORMERS_HOME="/data/models"
    
    # Create project directories if they don't exist
    mkdir -p "${RAGEX_PROJECT_DATA_DIR}"
    mkdir -p "${RAGEX_CHROMA_PERSIST_DIR}"
    mkdir -p "/data/models"
    
    # Create project metadata file
    cat > "${RAGEX_PROJECT_DATA_DIR}/project_info.json" << EOF
{
    "project_name": "${PROJECT_NAME}",
    "workspace_path": "${WORKSPACE_PATH:-unknown}",
    "created_at": "$(date -Iseconds)",
    "embedding_model": "${RAGEX_EMBEDDING_MODEL:-fast}",
    "collection_name": "${RAGEX_CHROMA_COLLECTION}"
}
EOF
    
    # Only show project info for non-search commands or if log level is INFO or DEBUG
    if [[ ! "$1" =~ ^search ]] || [[ "${RAGEX_LOG_LEVEL^^}" == "INFO" ]] || [[ "${RAGEX_LOG_LEVEL^^}" == "DEBUG" ]]; then
        echo "📁 Project: ${PROJECT_NAME}"
        echo "📊 Data dir: ${RAGEX_PROJECT_DATA_DIR}"
        echo "🔧 Embedding model: ${RAGEX_EMBEDDING_MODEL:-fast}"
    fi
}

# Initialize project-specific data directories
setup_project_data "$@"

# Handle different commands
case "$1" in
    "init")
        check_workspace
        # Create .mcpignore in the workspace
        if [ -f "/workspace/.mcpignore" ]; then
            echo "✅ .mcpignore already exists in current directory"
        else
            exec python -c "from src.ignore.init import init_ignore_file; from pathlib import Path; init_ignore_file(Path('/workspace'))"
        fi
        ;;
    "index")
        check_workspace
        shift
        # Pass the workspace directory and ensure correct persist dir
        export RAGEX_INDEX_PATH="/workspace"
        
        # Parse arguments properly
        path=""
        args=()
        while [ $# -gt 0 ]; do
            case "$1" in
                --*|-*)
                    # This is a flag, add it to args
                    args+=("$1")
                    ;;
                *)
                    # This is the path argument
                    if [ -z "$path" ]; then
                        path="$1"
                    else
                        # Additional non-flag argument
                        args+=("$1")
                    fi
                    ;;
            esac
            shift
        done
        
        # Default path to current directory (workspace)
        if [ -z "$path" ] || [ "$path" = "." ]; then
            path="/workspace"
        fi
        
        # Execute with properly ordered arguments
        exec python scripts/build_semantic_index.py "$path" "${args[@]}"
        ;;
    "serve"|"server")
        exec python -m src.server
        ;;
    "search")
        shift
        export RAGEX_CHROMA_PERSIST_DIR="${RAGEX_PROJECT_DATA_DIR}/chroma_db"
        # Suppress .mcpignore warnings for search commands
        export RAGEX_IGNOREFILE_WARNING=false
        # Disable logging setup override
        export RAGEX_DISABLE_LOGGING_SETUP=true
        exec python ragex_search.py --index-dir "${RAGEX_PROJECT_DATA_DIR}" "$@"
        ;;
    "list-projects")
        echo "📋 Available projects:"
        if [ -d "/data/projects" ]; then
            for project_dir in /data/projects/*/; do
                if [ -d "$project_dir" ]; then
                    project_name=$(basename "$project_dir")
                    if [ -f "${project_dir}project_info.json" ]; then
                        workspace_path=$(jq -r '.workspace_path // "unknown"' "${project_dir}project_info.json" 2>/dev/null || echo "unknown")
                        model=$(jq -r '.embedding_model // "unknown"' "${project_dir}project_info.json" 2>/dev/null || echo "unknown")
                        echo "  • ${project_name} (${workspace_path}) [${model}]"
                    else
                        echo "  • ${project_name}"
                    fi
                fi
            done
        else
            echo "  No projects found."
        fi
        ;;
    "clean-project")
        if [ -n "$2" ]; then
            project_to_clean="$2"
            if [ -d "/data/projects/${project_to_clean}" ]; then
                echo "🗑️  Removing project data for: ${project_to_clean}"
                rm -rf "/data/projects/${project_to_clean}"
                echo "✅ Project ${project_to_clean} data removed."
            else
                echo "❌ Project ${project_to_clean} not found."
                exit 1
            fi
        else
            echo "❌ Usage: clean-project <project_name>"
            exit 1
        fi
        ;;
    "info")
        # Show project info without needing workspace
        if [ -f "${RAGEX_PROJECT_DATA_DIR}/project_info.json" ]; then
            echo "📊 Project Information:"
            cat "${RAGEX_PROJECT_DATA_DIR}/project_info.json" | jq .
            
            # Check if ChromaDB exists and has data
            if [ -d "${RAGEX_CHROMA_PERSIST_DIR}" ]; then
                echo ""
                echo "📈 Index Statistics:"
                python -c "
from src.vector_store import VectorStore
from src.embedding_manager import EmbeddingManager
try:
    em = EmbeddingManager()
    vs = VectorStore(em)
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
        shift
        export RAGEX_CHROMA_PERSIST_DIR="${RAGEX_PROJECT_DATA_DIR}/chroma_db"
        # Suppress .mcpignore warnings for search commands
        export RAGEX_IGNOREFILE_WARNING=false
        # Disable logging setup override
        export RAGEX_DISABLE_LOGGING_SETUP=true
        exec python ragex_search.py --index-dir "${RAGEX_PROJECT_DATA_DIR}" "$@"
        ;;
    "bash"|"sh")
        exec "$@"
        ;;
    *)
        # Default to MCP server
        exec python -m src.server "$@"
        ;;
esac