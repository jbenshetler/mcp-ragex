#!/bin/bash
# ragex - Smart Docker wrapper for MCP-RageX with project isolation
set -e

# Default configuration
# Note: ragex:local is the locally built image with socket daemon support
# The public image ragex/mcp-server:latest doesn't have daemon support yet
DOCKER_IMAGE="${RAGEX_IMAGE:-${RAGEX_DOCKER_IMAGE:-ragex:local}}"
DOCKER_USER_ID=$(id -u)
DOCKER_GROUP_ID=$(id -g)

# Function to generate consistent project identifier
generate_project_id() {
    local workspace_path="$1"
    local user_id="$2"
    
    # Create a consistent project ID based on user and absolute workspace path
    local abs_path=$(cd "$workspace_path" 2>/dev/null && pwd || echo "$workspace_path")
    local project_hash=$(echo "${user_id}:${abs_path}" | sha256sum | cut -d' ' -f1 | head -c 16)
    echo "ragex_${user_id}_${project_hash}"
}

# Function to get project name for display
get_project_name() {
    local workspace_path="$1"
    local abs_path=$(cd "$workspace_path" 2>/dev/null && pwd || echo "$workspace_path")
    echo "$(basename "$abs_path")"
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: ragex [COMMAND] [OPTIONS]

Quick Start:
  1. ragex index .   # Index your project (starts daemon automatically)
  2. ragex search "query"  # Search your codebase

Commands:
  start              Index current directory (alias for 'index .')
  index [PATH]       Build semantic index and start daemon
  search QUERY       Search in current project
  ls [ID|ID_GLOB]    List projects (optional glob filter, -l for details)
  rm ID|ID_GLOB      Remove project(s) by ID or glob
  init               Create .mcpignore file in current directory
  info               Show project information
  register           Show registration instructions
  unregister         Show unregistration instructions
  log [PROJECT] [-f] Show/follow logs (global or per-project)
  bash               Get shell in container
  stop               Stop daemon if running
  status             Check daemon status
  
Environment Variables:
  RAGEX_EMBEDDING_MODEL    Embedding model preset (fast/balanced/accurate)
  RAGEX_PROJECT_NAME       Override project name
  RAGEX_DOCKER_IMAGE       Docker image to use
  RAGEX_DAEMON_ENABLED     Enable daemon mode (true/false)
  
Examples:
  ragex index .                    # Index current directory
  ragex search "auth functions"    # Search current project
  ragex ls                         # Show all your projects
  ragex log mcp-ragex -f           # Follow logs for specific project
  RAGEX_EMBEDDING_MODEL=balanced ragex index .  # Use balanced model
EOF
}

# Parse command line arguments
COMMAND="serve"
if [ $# -gt 0 ]; then
    COMMAND="$1"
    shift
fi

# Debug output
if [ "${RAGEX_DEBUG}" = "true" ]; then
    echo "[DEBUG] Command: $COMMAND, Args: $@" >&2
    echo "[DEBUG] Docker image: ${DOCKER_IMAGE}" >&2
fi

# Handle help/usage
if [ "$COMMAND" = "help" ] || [ "$COMMAND" = "--help" ] || [ "$COMMAND" = "-h" ]; then
    show_usage
    exit 0
fi

# Determine workspace path
WORKSPACE_PATH="${PWD}"
if [ "$COMMAND" = "index" ] && [ $# -gt 0 ]; then
    WORKSPACE_PATH="$1"
fi

# Always convert to absolute path
WORKSPACE_PATH=$(realpath "$WORKSPACE_PATH")

# Generate project-specific identifiers
USER_VOLUME="ragex_user_${DOCKER_USER_ID}"
PROJECT_ID=$(generate_project_id "$WORKSPACE_PATH" "$DOCKER_USER_ID")
PROJECT_NAME=$(get_project_name "$WORKSPACE_PATH")
DAEMON_CONTAINER_NAME="ragex_daemon_${PROJECT_ID}"

# Function to check if daemon is running
is_daemon_running() {
    docker ps -q -f "name=${DAEMON_CONTAINER_NAME}" | grep -q .
}

# Function to start daemon
start_daemon() {
    if is_daemon_running; then
        return 0
    fi
    
    echo "🚀 Starting ragex daemon for ${PROJECT_NAME}..."
    # if [ "${RAGEX_DEBUG}" = "true" ]; then
    #     echo "[DEBUG] Starting daemon container: ${DAEMON_CONTAINER_NAME}" >&2
    #     echo "[DEBUG] Docker image: ${DOCKER_IMAGE}" >&2
    # fi
    
    docker run -d \
        --name "${DAEMON_CONTAINER_NAME}" \
        -u "${DOCKER_USER_ID}:${DOCKER_GROUP_ID}" \
        -v "${USER_VOLUME}:/data" \
        -v "${WORKSPACE_PATH}:/workspace:ro" \
        -e "WORKSPACE_PATH=${WORKSPACE_PATH}" \
        -e "PROJECT_NAME=${PROJECT_ID}" \
        -e "RAGEX_EMBEDDING_MODEL=${RAGEX_EMBEDDING_MODEL:-fast}" \
        -e "HOST_HOME=${HOME}" \
        "${DOCKER_IMAGE}" daemon > /dev/null
    
    # Wait for daemon to be ready
    sleep 2
    
    # Wait for socket to be created (up to 10 seconds)
    local wait_count=0
    while [ $wait_count -lt 10 ]; do
        if docker exec "${DAEMON_CONTAINER_NAME}" test -S /tmp/ragex.sock 2>/dev/null; then
            echo "✅ Socket daemon is ready"
            return 0
        fi
        sleep 1
        wait_count=$((wait_count + 1))
    done
    
    # If socket not found, check if container is still running
    if is_daemon_running; then
        echo "⚠️  Daemon container is running but socket not found"
        echo "   Checking daemon logs..."
        docker logs --tail 20 "${DAEMON_CONTAINER_NAME}" 2>&1
        echo "❌ Failed to start socket daemon properly"
        # Stop the broken daemon
        docker stop "${DAEMON_CONTAINER_NAME}" > /dev/null 2>&1 || true
        docker rm "${DAEMON_CONTAINER_NAME}" > /dev/null 2>&1 || true
        return 1
    else
        echo "❌ Daemon container exited"
        # Show logs to help debug
        docker logs --tail 20 "${DAEMON_CONTAINER_NAME}" 2>&1 || true
        docker rm "${DAEMON_CONTAINER_NAME}" > /dev/null 2>&1 || true
        return 1
    fi
}

# Function to stop daemon
stop_daemon() {
    if ! is_daemon_running; then
        echo "ℹ️  No daemon running for ${PROJECT_NAME}"
        return 0
    fi
    
    echo "🛑 Stopping ragex daemon..."
    docker stop "${DAEMON_CONTAINER_NAME}" > /dev/null
    docker rm "${DAEMON_CONTAINER_NAME}" > /dev/null
    echo "✅ Daemon stopped"
}

# Function to get daemon status
daemon_status() {
    if is_daemon_running; then
        echo "✅ Daemon is running for ${PROJECT_NAME}"
        docker ps -f "name=${DAEMON_CONTAINER_NAME}" --format "table {{.ID}}\t{{.Status}}\t{{.Names}}"
    else
        echo "❌ No daemon running for ${PROJECT_NAME}"
    fi
}

# Function to execute command via daemon
exec_via_daemon() {
    local cmd="$1"
    shift
    
    # Debug output
    if [ "${RAGEX_DEBUG}" = "true" ]; then
        echo "[DEBUG] exec_via_daemon: cmd=$cmd, daemon_name=${DAEMON_CONTAINER_NAME}" >&2
    fi
    
    # Start daemon if not running
    if ! is_daemon_running; then
        if [ "${RAGEX_DEBUG}" = "true" ]; then
            echo "[DEBUG] Daemon not running, starting..." >&2
        fi
        start_daemon || return 1
    else
        if [ "${RAGEX_DEBUG}" = "true" ]; then
            echo "[DEBUG] Daemon already running" >&2
        fi
        :  # No-op to ensure else block has content
    fi
    
    # Determine if we need TTY
    local EXEC_FLAGS="-i"
    if [ -t 0 ] && [ "$cmd" != "serve" ] && [ "$cmd" != "server" ]; then
        EXEC_FLAGS="-it"
    fi
    
    # Execute command via docker exec using socket client
    if [ "${RAGEX_DEBUG}" = "true" ]; then
        echo "[DEBUG] Running: docker exec $EXEC_FLAGS ${DAEMON_CONTAINER_NAME} python -m src.socket_client $cmd $@" >&2
    fi
    docker exec $EXEC_FLAGS "${DAEMON_CONTAINER_NAME}" python -m src.socket_client "$cmd" "$@"
}

# Build Docker command
DOCKER_ARGS=(
    "run"
    "--rm"
    "-u" "${DOCKER_USER_ID}:${DOCKER_GROUP_ID}"
    "-v" "${USER_VOLUME}:/data"
    "-v" "${WORKSPACE_PATH}:/workspace:ro"
    "-e" "WORKSPACE_PATH=${WORKSPACE_PATH}"
    "-e" "PROJECT_NAME=${PROJECT_ID}"
    "-e" "RAGEX_EMBEDDING_MODEL=${RAGEX_EMBEDDING_MODEL:-fast}"
)

# Handle different command types
case "$COMMAND" in
    "bash"|"sh")
        # Interactive shell needs TTY
        DOCKER_ARGS+=("-it")
        ;;
    "serve"|"server")
        # MCP server needs stdin/stdout but NO TTY (breaks JSON-RPC)
        DOCKER_ARGS+=("-i")
        ;;
    *)
        # Other commands can be interactive if terminal is available
        if [ -t 0 ]; then
            DOCKER_ARGS+=("-it")
        fi
        ;;
esac

# Handle daemon-specific commands
case "$COMMAND" in
    "stop")
        stop_daemon
        exit $?
        ;;
    "status")
        daemon_status
        exit $?
        ;;
esac

# Handle special commands that don't need workspace
case "$COMMAND" in
    "ls"|"rm"|"register"|"unregister")
        # These commands don't use daemon, run directly
        DOCKER_ARGS=(
            "run"
            "--rm"
            "-u" "${DOCKER_USER_ID}:${DOCKER_GROUP_ID}"
            "-v" "${USER_VOLUME}:/data"
            "-e" "PROJECT_NAME=admin"
            "-e" "HOST_HOME=${HOME}"
            "-e" "HOST_USER=${USER}"
            "-e" "WORKSPACE_PATH=${WORKSPACE_PATH}"
        )
        exec docker "${DOCKER_ARGS[@]}" "$DOCKER_IMAGE" "$COMMAND" "$@"
        ;;
    "info")
        echo "🔧 RageX Project Information"
        echo "   User ID: ${DOCKER_USER_ID}"
        echo "   Workspace: ${WORKSPACE_PATH}"
        echo "   Project ID: ${PROJECT_ID}"
        echo "   Project Name: ${PROJECT_NAME}"
        echo "   User Volume: ${USER_VOLUME}"
        echo "   Docker Image: ${DOCKER_IMAGE}"
        echo "   Embedding Model: ${RAGEX_EMBEDDING_MODEL:-fast}"
        echo ""
        daemon_status
        exit 0
        ;;
    "log")
        # Handle log command - view logs from daemon containers
        project_identifier=""
        docker_args=()
        
        # Parse arguments
        while [ $# -gt 0 ]; do
            case "$1" in
                -f|--follow)
                    docker_args+=("--follow")
                    shift
                    ;;
                --tail)
                    docker_args+=("--tail" "$2")
                    shift 2
                    ;;
                --since)
                    docker_args+=("--since" "$2")
                    shift 2
                    ;;
                --until)
                    docker_args+=("--until" "$2")
                    shift 2
                    ;;
                -t|--timestamps)
                    docker_args+=("--timestamps")
                    shift
                    ;;
                --details)
                    docker_args+=("--details")
                    shift
                    ;;
                -*)
                    # Pass through unknown docker logs flags
                    docker_args+=("$1")
                    shift
                    ;;
                *)
                    if [ -z "$project_identifier" ]; then
                        project_identifier="$1"
                    else
                        echo "❌ Error: Multiple project identifiers specified: '$project_identifier' and '$1'"
                        exit 1
                    fi
                    shift
                    ;;
            esac
        done
        
        if [ -n "$project_identifier" ]; then
            # Per-project logs - resolve project name to project ID
            resolved_id=$(docker run --rm \
                -v "${USER_VOLUME}:/data" \
                --entrypoint python \
                "${DOCKER_IMAGE}" \
                -m src.ragex_core.project_resolver "$project_identifier" 2>&1)
            
            if [ $? -ne 0 ]; then
                # Resolution failed - show error message
                echo "$resolved_id" | sed 's/^ERROR: /❌ /'
                exit 1
            fi
            
            project_id="$resolved_id"
            container_name="ragex_daemon_${project_id}"
            
            # Check if container exists and is running
            if docker ps -q -f "name=${container_name}" | grep -q .; then
                # Show which project we resolved to (if different from input)
                if [ "$project_identifier" != "$project_id" ]; then
                    echo "📋 Logs for project: $project_identifier [$project_id]"
                else
                    echo "📋 Logs for project: $project_id"
                fi
                docker logs "${container_name}" "${docker_args[@]}"
            else
                echo "❌ No running daemon found for project: $project_identifier"
                if [ "$project_identifier" != "$project_id" ]; then
                    echo "   (Resolved to: $project_id)"
                fi
                echo ""
                echo "Available daemon containers:"
                daemon_containers=$(docker ps --format "{{.Names}}" | grep "^ragex_daemon_" | sed 's/ragex_daemon_/  /')
                if [ -n "$daemon_containers" ]; then
                    echo "$daemon_containers"
                else
                    echo "  (none)"
                fi
                echo ""
                echo "Start a daemon with: ragex start"
                exit 1
            fi
        else
            # Global logs - show all daemon containers
            daemon_containers=$(docker ps --format "{{.Names}}" | grep "^ragex_daemon_" | sort)
            
            if [ -z "$daemon_containers" ]; then
                echo "📋 No ragex daemon containers are currently running"
                echo ""
                echo "Start a daemon with: ragex start"
                exit 0
            fi
            
            echo "📋 Global ragex logs from all daemon containers:"
            echo ""
            
            for container in $daemon_containers; do
                project_id=${container#ragex_daemon_}
                echo "=== $project_id ==="
                docker logs "$container" "${docker_args[@]}" --tail 10 2>&1 | head -20
                echo ""
            done
        fi
        exit 0
        ;;
esac

# For all other commands, use daemon if available
case "$COMMAND" in
    "init"|"index"|"search"|"serve"|"server"|"bash"|"sh")
        # These commands benefit from daemon mode
        exec_via_daemon "$COMMAND" "$@"
        ;;
    *)
        # Unknown command - show error and usage
        echo "❌ Error: Unknown command '$COMMAND'"
        echo ""
        show_usage
        exit 1
        ;;
esac