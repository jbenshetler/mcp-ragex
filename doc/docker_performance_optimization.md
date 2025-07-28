# Docker Container Performance Optimization Plan

## Problem Analysis

### Current Behavior
The `ragex` command currently uses `docker run --rm` for every invocation, which means:
- A new container is created for each command
- The container is destroyed after the command completes
- No state is preserved between commands

### Performance Impact
- **Observed**: ~10 seconds to run `ragex search` on a project with <250 files
- **Breakdown of overhead**:
  - Docker container creation/destruction: ~1-2 seconds
  - Python interpreter startup: ~0.5 seconds
  - Loading heavy dependencies: ~3-4 seconds
    - sentence-transformers
    - chromadb
    - tree-sitter and language parsers
    - PyTorch/NumPy dependencies
  - Model loading (even from cache): ~2-3 seconds
  - Actual search operation: <1 second

### Root Causes
1. **Container lifecycle overhead**: Starting and stopping containers repeatedly
2. **Cold start penalty**: Python and all dependencies loaded from scratch each time
3. **No process reuse**: Models and indexes loaded fresh for each command
4. **I/O overhead**: Reading cached models from disk instead of keeping in memory

## Proposed Solutions

### Option 1: Persistent Background Container (Recommended)

#### Overview
Implement a daemon mode where a container runs persistently in the background and commands are executed via `docker exec`.

#### Technical Approach
```bash
# Start daemon
ragex start     # Starts persistent container
ragex stop      # Stops persistent container  
ragex status    # Shows if container is running

# Regular commands use docker exec when daemon is running
ragex search "query"  # Fast execution via docker exec
ragex index .         # Reuses loaded models
```

#### Implementation Details
1. **Container Management**:
   ```bash
   # Start container with specific name
   docker run -d --name "ragex_daemon_${PROJECT_ID}" \
     --rm \
     -v "${USER_VOLUME}:/data" \
     -v "${WORKSPACE_PATH}:/workspace:ro" \
     "${DOCKER_IMAGE}" daemon
   ```

2. **Command Routing**:
   ```bash
   # Check if daemon is running
   if docker ps -q -f "name=ragex_daemon_${PROJECT_ID}" > /dev/null; then
     # Use docker exec for fast execution
     docker exec -i "ragex_daemon_${PROJECT_ID}" "$COMMAND" "$@"
   else
     # Fall back to docker run
     docker run --rm ... "$COMMAND" "$@"
   fi
   ```

3. **Daemon Process**:
   - Long-running Python process that keeps models loaded
   - Accepts commands via stdin or simple socket
   - Maintains warm caches and indexes

#### Pros
- Near-instant command execution after first start
- Reuses loaded models and dependencies
- Minimal changes to existing architecture
- Backward compatible (works without daemon)

#### Cons
- Requires daemon management commands
- Uses memory while idle
- Need to handle daemon crashes/recovery

### Option 2: Lightweight Native Client

#### Overview
Install a minimal Python client locally that handles simple operations and delegates to Docker for heavy tasks.

#### Technical Approach
```
ragex (native) -> decides if local or docker
  ├── Simple grep/ripgrep searches -> local execution
  └── Semantic search/indexing -> docker container
```

#### Implementation Details
1. **Native client** (`pip install ragex-cli`):
   - Minimal dependencies (just `click`, `requests`)
   - Handles argument parsing and routing
   - Executes ripgrep directly for simple searches

2. **Docker service** (for heavy operations):
   - Runs only when needed for semantic search
   - Can still use persistent mode for these operations

#### Pros
- Instant execution for simple searches
- No daemon management needed
- Reduced Docker overhead for common operations

#### Cons
- Requires local Python installation
- More complex deployment (two components)
- Feature disparity between local and Docker

### Option 3: Pre-warmed Container Pool

#### Overview
Maintain a pool of pre-started containers ready to handle commands.

#### Technical Approach
1. After first command, start a new container in background
2. Next command swaps in the pre-warmed container
3. Immediately start warming another container

#### Pros
- Fast execution without explicit daemon management
- Automatic lifecycle management
- Good for intermittent usage patterns

#### Cons
- Complex implementation
- Race conditions to handle
- Wasted resources if not used

## Recommended Implementation Plan

### Phase 1: Basic Daemon Functionality (1-2 days)

1. **Add daemon commands to `ragex` script**:
   ```bash
   ragex start   # Start background container
   ragex stop    # Stop background container
   ragex status  # Check daemon status
   ```

2. **Implement daemon mode in `entrypoint.sh`**:
   ```python
   # New daemon.py
   class RagexDaemon:
       def __init__(self):
           self.load_models()
           self.setup_indexes()
       
       def handle_command(self, cmd, args):
           # Route to appropriate handler
   ```

3. **Update command routing**:
   - Check for running daemon first
   - Use `docker exec` if available
   - Fall back to `docker run` if not

### Phase 2: Auto-start and Health Checks (1 day)

1. **Auto-start daemon on first command**:
   ```bash
   if ! docker ps -q -f "name=ragex_daemon_${PROJECT_ID}"; then
     ragex start --quiet
   fi
   ```

2. **Health check endpoint**:
   - Simple file-based check: `/tmp/ragex_healthy`
   - Or HTTP endpoint on internal port

3. **Automatic recovery**:
   - Detect unhealthy daemon
   - Restart automatically
   - Retry command

### Phase 3: Advanced Features (2-3 days)

1. **Idle timeout**:
   - Stop daemon after N minutes of inactivity
   - Configurable via environment variable
   - Graceful shutdown

2. **Memory optimization**:
   - Lazy loading of models
   - Unload models not used recently
   - Configurable memory limits

3. **Multi-project support**:
   - One daemon per project
   - Shared model cache
   - Resource limits per daemon

## Performance Expectations

### Current Performance
- First search: ~10 seconds
- Subsequent searches: ~10 seconds each

### With Persistent Container
- First search: ~10 seconds (starts daemon)
- Subsequent searches: <0.5 seconds
- Overhead: ~100-200ms for docker exec

### Performance Gains
- **20x faster** for subsequent operations
- Near-native performance for all commands
- Especially beneficial for iterative workflows

## Configuration Options

```bash
# Environment variables
RAGEX_DAEMON_ENABLED=true          # Enable daemon mode
RAGEX_DAEMON_TIMEOUT=300           # Stop after 5 min idle
RAGEX_DAEMON_MEMORY_LIMIT=2g       # Memory limit
RAGEX_DAEMON_AUTO_START=true       # Auto-start on first command
```

## Migration Path

1. **Phase 1**: Implement daemon as opt-in feature
   - Users explicitly run `ragex start`
   - Document performance benefits

2. **Phase 2**: Make daemon default with auto-start
   - Transparent to users
   - Add `--no-daemon` flag for old behavior

3. **Phase 3**: Deprecate non-daemon mode
   - Simplify codebase
   - Focus on daemon performance

## Testing Strategy

1. **Unit tests**:
   - Daemon lifecycle management
   - Command routing logic
   - Health check functionality

2. **Integration tests**:
   - Multi-command workflows
   - Daemon crash recovery
   - Resource cleanup

3. **Performance tests**:
   - Measure command latency
   - Memory usage over time
   - Concurrent command handling

## Security Considerations

1. **Container isolation**: Each user/project gets separate daemon
2. **Resource limits**: Prevent runaway memory/CPU usage
3. **Access control**: Daemon only accessible to launching user
4. **Cleanup**: Ensure daemons are stopped on system shutdown

## Conclusion

The persistent container approach offers the best balance of performance improvement and implementation complexity. It can deliver 20x performance improvements for subsequent commands while maintaining backward compatibility and requiring minimal changes to the existing architecture.

The phased implementation plan allows for incremental delivery of value, starting with basic daemon functionality and progressively adding more sophisticated features based on user feedback and usage patterns.