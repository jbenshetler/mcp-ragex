# MCP Server stdio Cleanup Implementation Plan

## Problem Statement

The MCP (Model Context Protocol) server requires exclusive, clean access to stdin/stdout/stderr for JSON protocol communication. However, the current implementation has potential contamination points that could corrupt the MCP communication stream with extraneous output.

## Current MCP Communication Flow

```
MCP Client ↔ ragex --mcp ↔ docker exec ↔ container:src.server
```

The critical requirement: **Only `src.server` (the actual MCP server) should write to stdout/stderr after MCP protocol begins.**

## Contamination Points Identified

### 1. Daemon Startup Phase (Pre-MCP)
```python
def run_mcp_mode(self) -> int:
    # CONTAMINATION RISK: Output before MCP server starts
    if not self.start_daemon(silent=True):  # ← Potential Docker output
        return 1
    
    # Only after daemon ready do we start clean MCP server
    docker_cmd = ['docker', 'exec', '-i', self.daemon_container_name,
                  'python', '-m', 'src.socket_client', 'mcp']
```

**Sources of contamination:**
- Docker container creation messages
- Image pull notifications  
- Socket readiness check output
- Error messages during daemon startup

### 2. Container Startup Logs
Even with `silent=True`, Docker itself might emit to stderr:
```bash
"Unable to find image 'ragex:local' locally"
"Pulling from library/ragex"  
"Container ragex_daemon_xyz started"
```

### 3. Background Daemon Interference
The daemon container runs continuously and might have logging that could interfere with MCP stdio if improperly connected.

### 4. Python Environment Warnings
Model loading, imports, and library initialization could emit warnings:
```python
# Suppressed in indexer.py but might leak elsewhere
warnings.filterwarnings("ignore", message=".*encoder_attention_mask.*", category=FutureWarning)
```

## Solution Architecture

### Principle: Isolate Pre-MCP Setup from MCP Communication

The solution is to **completely suppress all output during daemon setup**, then **provide clean stdio to the MCP server**.

```
Phase 1: Setup (Suppressed)    Phase 2: MCP Communication (Clean)
┌─────────────────────────┐    ┌──────────────────────────────┐
│ Daemon startup          │    │ MCP Server                   │
│ Container checks        │ →  │ stdin/stdout/stderr          │
│ Socket verification     │    │ exclusively for JSON         │
│ (ALL OUTPUT SUPPRESSED) │    │ protocol communication      │
└─────────────────────────┘    └──────────────────────────────┘
```

## Implementation Plan

### 1. Enhanced Pre-MCP Setup Isolation

**File:** `ragex` (CLI script)

```python
def run_mcp_mode(self) -> int:
    """Run as MCP server with clean stdio isolation"""
    
    # Phase 1: Setup with complete output suppression
    setup_success = self._setup_daemon_for_mcp()
    if not setup_success:
        # Exit silently - MCP client will handle error detection
        return 1
    
    # Phase 2: Start MCP server with clean stdio
    return self._start_clean_mcp_server()

def _setup_daemon_for_mcp(self) -> bool:
    """Set up daemon with complete output suppression"""
    
    # Suppress ALL output during setup phase
    with open(os.devnull, 'w') as devnull:
        # Temporarily redirect stdout/stderr during setup
        old_stdout, old_stderr = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = devnull
        
        try:
            # Check if daemon is already running
            if self.is_daemon_running():
                return True
            
            # Start daemon with complete output suppression
            return self._start_daemon_silent()
            
        except Exception:
            # Any setup errors should not leak to MCP protocol
            return False
        finally:
            # Always restore stdio
            sys.stdout, sys.stderr = old_stdout, old_stderr

def _start_daemon_silent(self) -> bool:
    """Start daemon with zero output leakage"""
    
    # Docker run command for daemon
    docker_cmd = [
        'docker', 'run', '-d',  # Detached mode
        '--name', self.daemon_container_name,
        '-u', f'{self.user_id}:{self.group_id}',
        '-v', f'{self.user_volume}:/data',
        '-v', f'{self.workspace_path}:/workspace:ro',
        '-e', f'WORKSPACE_PATH={self.workspace_path}',
        '-e', f'PROJECT_NAME={self.project_id}',
        '-e', f'RAGEX_EMBEDDING_MODEL={self.embedding_model}',
        '-e', f'HOST_HOME={Path.home()}',
        '-e', f'RAGEX_LOG_LEVEL=ERROR',  # Suppress daemon logs
        '-e', 'PYTHONWARNINGS=ignore',   # Suppress Python warnings
        self.docker_image,
        'daemon'
    ]
    
    # Completely suppress Docker output
    result = subprocess.run(docker_cmd, 
                           stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL)
    
    if result.returncode != 0:
        return False
    
    # Wait for socket readiness (silently)
    return self._wait_for_socket_silent()

def _wait_for_socket_silent(self) -> bool:
    """Wait for daemon socket with no output"""
    
    for i in range(10):  # 10 second timeout
        time.sleep(1)
        
        # Check socket availability (suppress all output)
        check_result = subprocess.run(
            ['docker', 'exec', self.daemon_container_name, 
             'test', '-S', '/tmp/ragex.sock'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        if check_result.returncode == 0:
            return True
    
    # Cleanup failed daemon (silently)
    subprocess.run(['docker', 'stop', self.daemon_container_name], 
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(['docker', 'rm', self.daemon_container_name], 
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return False

def _start_clean_mcp_server(self) -> int:
    """Start MCP server with exclusive stdio access"""
    
    # Build clean MCP server command
    docker_cmd = [
        'docker', 'exec', 
        '-i',  # Interactive stdin, NO tty (-t) for MCP
        self.daemon_container_name,
        'python', '-m', 'src.socket_client', 'mcp'
    ]
    
    # Pass through stdin/stdout/stderr exclusively to MCP server
    # This is the ONLY process that should write to stdout after this point
    result = subprocess.run(docker_cmd, 
                           stdin=sys.stdin, 
                           stdout=sys.stdout, 
                           stderr=sys.stderr)
    return result.returncode
```

### 2. Container Environment Cleanup

**File:** `src/socket_client.py`

```python
def main():
    # ... existing code ...
    
    # Special handling for mcp command - clean environment
    if command == 'mcp':
        # Configure clean environment for MCP server
        os.environ['PYTHONWARNINGS'] = 'ignore'
        os.environ['RAGEX_LOG_LEVEL'] = 'ERROR'
        
        # Suppress any remaining warnings
        import warnings
        warnings.filterwarnings('ignore')
        
        # Direct exec to MCP server (takes over stdio completely)
        os.execvp('python', ['python', '-m', 'src.server'] + args)
        # Should not reach here
        sys.exit(1)
```

### 3. MCP Server Logging Configuration

**File:** `src/server.py`

```python
def main():
    """MCP server entry point with clean stdio"""
    
    # Ensure completely clean logging configuration
    logging.getLogger().handlers.clear()
    logging.getLogger().addHandler(logging.NullHandler())
    
    # Suppress all warnings
    import warnings
    warnings.filterwarnings('ignore')
    
    # Start MCP server with exclusive stdio access
    server = RagexMCPServer()
    server.run()
```

### 4. Daemon Container Logging Isolation

**File:** `docker/entrypoint.sh`

```bash
#!/bin/bash

# For daemon mode, ensure logs don't interfere with MCP
if [ "$1" = "daemon" ]; then
    # Redirect daemon logs to files, not stdout/stderr
    exec python -m src.socket_daemon \
        > /tmp/ragex_daemon.log 2>&1
else
    # Other modes can use normal stdio
    exec "$@"
fi
```

## Testing Strategy

### 1. MCP Protocol Validation
```bash
# Test that MCP communication is clean
echo '{"jsonrpc":"2.0","method":"ping","id":1}' | ragex --mcp
# Should receive ONLY valid JSON response, no other output
```

### 2. Daemon Startup Isolation
```bash
# Test daemon startup suppression
ragex --mcp &
PID=$!
sleep 2
# Check that no output appeared during startup
kill $PID
```

### 3. Container Log Isolation
```bash
# Verify daemon logs don't leak to MCP stdio
docker logs ragex_daemon_xxx  # Should show daemon logs
# But MCP communication should remain clean
```

## Error Handling Strategy

### Silent Failures During Setup
- Setup phase failures should **not** emit error messages to stdout/stderr
- MCP client will detect failure through connection timeout or protocol errors
- Error details can be logged to daemon logs for debugging

### MCP Server Errors
- Only the MCP server itself should emit error responses
- All errors must be valid JSON-RPC error responses
- No plain text error messages to stdout/stderr

## Benefits of This Approach

### 1. Clean Protocol Communication
- Guarantees MCP client receives only valid JSON responses
- Eliminates protocol corruption from Docker/daemon output
- Provides reliable MCP server operation

### 2. Robust Error Handling
- Setup failures don't break MCP protocol
- Clear separation between setup and communication phases
- Proper error recovery and cleanup

### 3. Maintainable Architecture
- Clear phase separation makes debugging easier
- Isolated components with defined responsibilities
- Easy to test each phase independently

### 4. Production Ready
- Handles Docker environment variations gracefully
- Suppresses environment-specific warnings and messages
- Reliable operation across different deployment scenarios

## Implementation Timeline

### Phase 1: Core stdio Isolation (Days 1-2)
- [ ] Implement `_setup_daemon_for_mcp()` with output suppression
- [ ] Add `_start_daemon_silent()` with DEVNULL redirection
- [ ] Update `run_mcp_mode()` with phase separation

### Phase 2: Container Environment (Days 3-4)
- [ ] Update `src/socket_client.py` MCP command handling
- [ ] Configure clean environment variables
- [ ] Update daemon container logging redirection

### Phase 3: Testing and Validation (Day 5)
- [ ] Test MCP protocol communication cleanliness
- [ ] Validate daemon startup suppression
- [ ] Comprehensive error handling testing

This implementation ensures that the MCP server has exclusive, clean access to stdio for proper JSON protocol communication while completely isolating all setup and daemon operations from the communication stream.