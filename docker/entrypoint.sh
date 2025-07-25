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
    export TRANSFORMERS_CACHE="/data/models"
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
    
    echo "📁 Project: ${PROJECT_NAME}"
    echo "📊 Data dir: ${RAGEX_PROJECT_DATA_DIR}"
    echo "🔧 Embedding model: ${RAGEX_EMBEDDING_MODEL:-fast}"
}

# Initialize project-specific data directories
setup_project_data

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
    "bash"|"sh")
        exec "$@"
        ;;
    *)
        # Default to MCP server
        exec python -m src.server "$@"
        ;;
esac