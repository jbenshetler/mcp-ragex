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
        # Use a hash of the workspace path for consistent project identification
        PROJECT_HASH=$(echo "$WORKSPACE_PATH" | sha256sum | cut -d' ' -f1 | head -c 16)
        PROJECT_NAME="${PROJECT_NAME:-project_${PROJECT_HASH}}"
    else
        PROJECT_NAME="${PROJECT_NAME:-admin}"
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
    
    # Create or update project metadata file
    if [ -f "${RAGEX_PROJECT_DATA_DIR}/project_info.json" ]; then
        # Update existing metadata - preserve created_at but update other fields
        created_at=$(jq -r '.created_at // ""' "${RAGEX_PROJECT_DATA_DIR}/project_info.json" 2>/dev/null || echo "")
        if [ -z "$created_at" ]; then
            created_at="$(date -Iseconds)"
        fi
    else
        created_at="$(date -Iseconds)"
    fi
    
    cat > "${RAGEX_PROJECT_DATA_DIR}/project_info.json" << EOF
{
    "project_name": "${PROJECT_NAME}",
    "workspace_path": "${WORKSPACE_PATH:-unknown}",
    "workspace_basename": "$(basename "${WORKSPACE_PATH:-unknown}")",
    "created_at": "${created_at}",
    "last_accessed": "$(date -Iseconds)",
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

# Handle different commands
case "$1" in
    "init")
        setup_project_data "$@"
        check_workspace
        # Create .mcpignore in the workspace
        if [ -f "/workspace/.mcpignore" ]; then
            echo "✅ .mcpignore already exists in current directory"
        else
            exec python -c "from src.lib.ignore.init import init_ignore_file; from pathlib import Path; init_ignore_file(Path('/workspace'))"
        fi
        ;;
    "index")
        setup_project_data "$@"
        check_workspace
        shift
        # Pass the workspace directory and ensure correct persist dir
        export RAGEX_INDEX_PATH="/workspace"
        # Suppress .mcpignore warnings for index command
        export RAGEX_IGNOREFILE_WARNING=false
        
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
        setup_project_data "$@"
        exec python -m src.server
        ;;
    "search")
        setup_project_data "$@"
        shift
        export RAGEX_CHROMA_PERSIST_DIR="${RAGEX_PROJECT_DATA_DIR}/chroma_db"
        # Suppress .mcpignore warnings for search commands
        export RAGEX_IGNOREFILE_WARNING=false
        # Disable logging setup override
        export RAGEX_DISABLE_LOGGING_SETUP=true
        exec python ragex_search.py --index-dir "${RAGEX_PROJECT_DATA_DIR}" "$@"
        ;;
    "list-projects"|"ls")
        # Check for --all flag
        show_all=false
        for arg in "$@"; do
            if [ "$arg" = "--all" ]; then
                show_all=true
                break
            fi
        done
        
        echo "📋 Available projects:"
        echo ""
        if [ -d "/data/projects" ]; then
            # Print header
            printf "%-50s %-10s %-8s %s\n" "PROJECT NAME [ID]" "MODEL" "INDEXED" "PATH"
            printf "%-50s %-10s %-8s %s\n" "--------------------------------------------------" "----------" "--------" "----"
            
            project_count=0
            for project_dir in /data/projects/*/; do
                if [ -d "$project_dir" ]; then
                    project_id=$(basename "$project_dir")
                    
                    # Skip admin project unless --all is specified
                    if [ "$project_id" = "admin" ] && [ "$show_all" = false ]; then
                        continue
                    fi
                    
                    project_count=$((project_count + 1))
                    
                    if [ -f "${project_dir}project_info.json" ]; then
                        workspace_path=$(jq -r '.workspace_path // "unknown"' "${project_dir}project_info.json" 2>/dev/null || echo "unknown")
                        workspace_basename=$(jq -r '.workspace_basename // ""' "${project_dir}project_info.json" 2>/dev/null || echo "")
                        model=$(jq -r '.embedding_model // "unknown"' "${project_dir}project_info.json" 2>/dev/null || echo "unknown")
                        
                        # Display project name from basename if available
                        if [ -n "$workspace_basename" ] && [ "$workspace_basename" != "unknown" ]; then
                            display_name="$workspace_basename [$project_id]"
                        else
                            # For old projects without basename, try to extract from path
                            if [ "$workspace_path" != "unknown" ]; then
                                path_basename=$(basename "$workspace_path")
                                display_name="$path_basename [$project_id]"
                            else
                                display_name="$project_id"
                            fi
                        fi
                        
                        # Check index status
                        if [ -d "${project_dir}chroma_db" ]; then
                            status="y"
                        else
                            status="n"
                        fi
                        
                        # Print row
                        printf "%-50s %-10s %-8s %s\n" \
                            "${display_name:0:50}" \
                            "$model" \
                            "$status" \
                            "$workspace_path"
                    else
                        printf "%-50s %-10s %-8s %s\n" \
                            "${project_id:0:50}" \
                            "-" \
                            "x" \
                            "No metadata"
                    fi
                fi
            done
            
            if [ $project_count -eq 0 ]; then
                echo "  No projects found."
            else
                echo ""
                echo "Total: $project_count project(s)"
                echo ""
                echo "Legend: y = indexed, n = not indexed, x = no metadata"
            fi
        else
            echo "  No projects found."
        fi
        ;;
    "clean-project"|"rm")
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
            echo "❌ Usage: rm <project_id>"
            exit 1
        fi
        ;;
    "register")
        shift
        # Handle register command and subcommands
        case "$1" in
            "claude")
                shift
                # Parse arguments
                scope="project"  # default
                verbose_mode=false
                while [ $# -gt 0 ]; do
                    case "$1" in
                        --scope)
                            shift
                            if [ -n "$1" ]; then
                                scope="$1"
                                shift
                            else
                                echo "❌ Error: --scope requires an argument (project or global)" >&2
                                exit 1
                            fi
                            ;;
                        --verbose)
                            verbose_mode=true
                            shift
                            ;;
                        *)
                            echo "❌ Error: Unknown argument: $1" >&2
                            echo "Usage: ragex register claude [--scope project|global] [--verbose]" >&2
                            exit 1
                            ;;
                    esac
                done
                
                # Validate scope
                if [ "$scope" != "project" ] && [ "$scope" != "global" ]; then
                    echo "❌ Error: Invalid scope '$scope'. Must be 'project' or 'global'" >&2
                    exit 1
                fi
                
                # Get host home directory (passed through Docker)
                # Use HOST_HOME if available, otherwise fall back to constructing path
                if [ -n "${HOST_HOME}" ]; then
                    RAGEX_BIN="${HOST_HOME}/.local/bin/ragex"
                else
                    # Fallback: construct from USER if HOST_HOME not set
                    RAGEX_BIN="/home/${USER}/.local/bin/ragex"
                fi
                
                # Build the command
                if [ "$scope" = "global" ]; then
                    REGISTER_CMD="claude mcp add ragex ${RAGEX_BIN}"
                else
                    REGISTER_CMD="claude mcp add ragex ${RAGEX_BIN} --scope project"
                fi
                
                # verbose_mode is already set from argument parsing above
                
                if [ "$verbose_mode" = true ]; then
                    # Human-readable output
                    echo "📝 To register MCP-RageX with Claude Code:"
                    echo ""
                    echo "  $REGISTER_CMD"
                    echo ""
                    echo "Run this command in your terminal to enable ragex in Claude Code."
                    if [ "$scope" = "project" ]; then
                        echo "This will enable ragex commands for all your projects."
                    else
                        echo "This will enable ragex commands globally."
                    fi
                else
                    # Machine-readable output for eval (default)
                    echo "$REGISTER_CMD"
                fi
                ;;
            "")
                # Show available registration options
                echo "🔧 MCP-RageX Registration"
                echo ""
                echo "Available registration targets:"
                echo "  claude    - Register with Claude Code"
                echo ""
                echo "Usage:"
                echo "  ragex register              # Show this help"
                echo "  ragex register claude       # Output command only (for eval)"
                echo "  ragex register claude --scope global   # Register globally"
                echo "  ragex register claude --scope project  # Explicitly set project scope"
                echo "  ragex register claude --verbose        # Show detailed instructions"
                echo ""
                echo "Examples:"
                echo "  eval \$(ragex register claude)         # Register automatically"
                echo "  ragex register claude --verbose        # Show registration instructions"
                ;;
            *)
                echo "❌ Error: Unknown registration target: $1"
                echo "Available targets: claude"
                echo "Run 'ragex register' for more information."
                exit 1
                ;;
        esac
        ;;
    "unregister")
        shift
        # Handle unregister command and subcommands
        case "$1" in
            "claude")
                shift
                # Parse arguments
                scope="project"  # default
                verbose_mode=false
                while [ $# -gt 0 ]; do
                    case "$1" in
                        --scope)
                            shift
                            if [ -n "$1" ]; then
                                scope="$1"
                                shift
                            else
                                echo "❌ Error: --scope requires an argument (project or global)" >&2
                                exit 1
                            fi
                            ;;
                        --verbose)
                            verbose_mode=true
                            shift
                            ;;
                        *)
                            echo "❌ Error: Unknown argument: $1" >&2
                            echo "Usage: ragex unregister claude [--scope project|global] [--verbose]" >&2
                            exit 1
                            ;;
                    esac
                done
                
                # Validate scope
                if [ "$scope" != "project" ] && [ "$scope" != "global" ]; then
                    echo "❌ Error: Invalid scope '$scope'. Must be 'project' or 'global'" >&2
                    exit 1
                fi
                
                # Build the unregister command
                if [ "$scope" = "global" ]; then
                    UNREGISTER_CMD="claude mcp remove ragex"
                else
                    UNREGISTER_CMD="claude mcp remove ragex --scope project"
                fi
                
                # verbose_mode is already set from argument parsing above
                
                if [ "$verbose_mode" = true ]; then
                    # Human-readable output
                    echo "🗑️  To unregister MCP-RageX from Claude Code:"
                    echo ""
                    echo "  $UNREGISTER_CMD"
                    echo ""
                    echo "Run this command in your terminal to remove ragex from Claude Code."
                    if [ "$scope" = "project" ]; then
                        echo "This will remove ragex commands from your projects."
                    else
                        echo "This will remove ragex commands globally."
                    fi
                else
                    # Machine-readable output for eval (default)
                    echo "$UNREGISTER_CMD"
                fi
                ;;
            "")
                # Show available unregistration options
                echo "🗑️  MCP-RageX Unregistration"
                echo ""
                echo "Available unregistration targets:"
                echo "  claude    - Unregister from Claude Code"
                echo ""
                echo "Usage:"
                echo "  ragex unregister            # Show this help"
                echo "  ragex unregister claude     # Output command only (for eval)"
                echo "  ragex unregister claude --scope global   # Unregister globally"
                echo "  ragex unregister claude --scope project  # Explicitly set project scope"
                echo "  ragex unregister claude --verbose        # Show detailed instructions"
                echo ""
                echo "Examples:"
                echo "  eval \$(ragex unregister claude)       # Unregister automatically"
                echo "  ragex unregister claude --verbose      # Show unregistration instructions"
                ;;
            *)
                echo "❌ Error: Unknown unregistration target: $1"
                echo "Available targets: claude"
                echo "Run 'ragex unregister' for more information."
                exit 1
                ;;
        esac
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
        setup_project_data "$@"
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
    *)
        # Unknown command
        echo "❌ Error: Unknown command '$1'"
        echo ""
        echo "Available commands:"
        echo "  init               Create .mcpignore file"
        echo "  index [PATH]       Build semantic index"
        echo "  search QUERY       Search in project"
        echo "  serve/server       Start MCP server"
        echo "  info               Show project information"
        echo "  ls                 List all projects"
        echo "  list-projects      List all projects (alias for ls)"
        echo "  rm ID              Remove project data"
        echo "  clean-project ID   Remove project data (alias for rm)"
        echo "  register           Show registration instructions"
        echo "  unregister         Show unregistration instructions"
        echo "  daemon             Start socket daemon (internal)"
        exit 1
        ;;
esac