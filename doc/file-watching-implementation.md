# File Watching Implementation

## Overview

RAGex now includes automatic file watching and incremental re-indexing. When you run `ragex index .`, it:
1. Starts a daemon for fast search performance
2. Builds a complete index of your codebase
3. Watches for file changes and automatically re-indexes them

## Key Features

### Content-Based Checksums
- Uses SHA256 hash of file contents (not modification times)
- Git-friendly: pull/checkout doesn't trigger unnecessary re-indexing
- `ragex index .` skips re-indexing if nothing changed

### Project Root Detection
- Running `ragex index .` in a subdirectory detects the project root
- Always maintains a single index per project
- Clear messaging shows what's happening

### Automatic Re-indexing
- File changes are detected immediately
- 60-second debounce period batches multiple changes
- Only changed files are re-indexed (incremental updates)
- Respects `.mcpignore` patterns

## Usage

### First Time
```bash
cd /path/to/project
ragex index .
# 🚀 Starting daemon for fast search...
# 📊 Indexing workspace...
# ✅ Indexed 1,234 files
# 👁️ Watching for file changes (60s debounce)...

ragex search "authentication"
# Results appear instantly
```

### Subsequent Runs
```bash
ragex index .
# ✅ Index is up-to-date
# 👁️ File watching active
```

### After File Changes
```bash
# Edit src/auth.py
# Wait ~60 seconds
# See in daemon logs:
# 📝 File changed: src/auth.py
# ⏱️ Waiting 60s for more changes...
# 🔄 Re-indexing 1 changed file...
# ✅ Re-indexed 1 file (15 symbols) in 0.3s
```

## Implementation Details

### Components
- `workspace_checksum.py`: Calculates content-based checksums
- `project_utils.py`: Handles project root detection
- `indexing_queue.py`: Batches file changes with debouncing
- `indexing_file_handler.py`: Watchdog event handler
- `socket_daemon.py`: Enhanced with file watching setup

### Architecture
1. Watchdog monitors filesystem events
2. Events filtered through `.mcpignore` patterns
3. Changes queued with 60-second debounce
4. Incremental indexing updates only changed files
5. Vector store updated in-place

### Performance
- Initial index: Same as before
- Checksum calculation: <1 second for most projects
- File watching: Negligible overhead
- Re-indexing: Only processes changed files

## Configuration

Currently uses sensible defaults:
- 60-second debounce period
- All code file extensions monitored
- File watching enabled automatically

Future enhancements could add:
- Configurable debounce period
- Pause/resume functionality
- Custom file patterns