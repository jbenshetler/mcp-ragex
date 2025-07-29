# Auto-Start Daemon Plan

## Current State
The daemon must be manually started with `ragex start` before users can see the performance benefits. This is not user-friendly and leads to confusion.

## Commands That Should Auto-Start the Daemon

### Primary Commands (benefit from daemon performance):
1. **`ragex search`** - Main use case, needs fast performance
2. **`ragex index`** - Benefits from pre-loaded modules
3. **`ragex init`** - Quick operation, benefits from instant startup

### Secondary Commands (optional daemon support):
4. **`ragex serve`/`ragex server`** - MCP server mode (could use daemon)
5. **`ragex register`** - Registration helper (could use daemon)

### Commands That Should NOT Auto-Start Daemon:
- `ragex start` - Explicitly starts daemon
- `ragex stop` - Explicitly stops daemon  
- `ragex status` - Checks daemon status
- `ragex info` - Shows project info (doesn't need daemon)
- `ragex list-projects` - Lists projects (doesn't need daemon)
- `ragex clean-project` - Removes project data (doesn't need daemon)
- `ragex bash`/`ragex sh` - Interactive shell (incompatible with daemon)

## Implementation Plan

### 1. Modify `exec_via_daemon` function in ragex wrapper
The function already attempts to start the daemon if not running:
```bash
if ! is_daemon_running; then
    start_daemon || return 1
fi
```

However, it seems to fail silently or not work as expected. Need to:
- Add better error handling
- Ensure start_daemon waits for socket to be ready
- Add retry logic if daemon fails to start

### 2. Add auto-start for specific commands
Currently, these commands go through `exec_via_daemon`:
- init, index, search, serve, server, bash, sh, register

We should:
- Keep auto-start for: init, index, search
- Make serve/server optional (add flag)
- Remove bash/sh from daemon execution (incompatible)

### 3. Improve daemon startup reliability
- Add health check endpoint in socket daemon
- Implement proper readiness check (not just socket existence)
- Add startup timeout and retry logic
- Better error messages when daemon fails to start

### 4. User Experience Improvements
- Show daemon startup message: "Starting search daemon (first time may take a few seconds)..."
- Cache daemon state to avoid repeated checks
- Add `--no-daemon` flag for users who prefer subprocess mode
- Document daemon behavior in help text

## Technical Changes Required

### ragex wrapper script:
1. Fix `start_daemon` function to properly wait for readiness
2. Add retry logic with exponential backoff
3. Improve error messages
4. Add `--no-daemon` flag support

### socket_daemon.py:
1. Add `/health` endpoint that returns ready status
2. Ensure socket is created early but only accept connections when ready
3. Add startup progress logging

### entrypoint.sh:
1. Update command routing for bash/sh to bypass daemon
2. Add daemon auto-start logic for specific commands

## Testing Strategy
1. Test cold start: `ragex stop && ragex search "test"`
2. Test warm start: `ragex search "test"` (second time)
3. Test failure recovery: Kill daemon process and run search
4. Test all commands to ensure proper daemon usage
5. Test `--no-daemon` flag functionality

## Success Metrics
- First search after cold start: <15 seconds (includes daemon startup)
- Subsequent searches: <1 second
- No manual `ragex start` required for common operations
- Clear feedback when daemon is starting
- Graceful fallback if daemon fails