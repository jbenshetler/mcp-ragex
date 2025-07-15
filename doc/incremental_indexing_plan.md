# Incremental Indexing Plan

## Overview

Implement automatic incremental indexing to keep the semantic search index up-to-date as code files change during active coding sessions. This system monitors file changes, debounces updates to handle chunked agent modifications, and intelligently triggers reindexing when the coding agent is still active.

## Goals

1. **Maintain Fresh Index**: Keep semantic search results current with code changes
2. **Handle Agent Workflows**: Account for how coding agents make changes in chunks
3. **Minimize Overhead**: Only reindex changed files, not entire codebase
4. **Smart Timing**: Update when agent is active but after changes have settled

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   File Watcher  │───▶│  Change Queue    │───▶│  Update Manager │
│   (watchdog)    │    │  (debounced)     │    │  (incremental)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Activity Tracker│    │  Batching Logic  │    │  Index Updater  │
│ (heartbeat)     │    │  (60s timeout)   │    │  (per-file)     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Implementation Plan

### Phase 1: File Change Detection

**File: `src/file_watcher.py`**

Core file monitoring system using watchdog library:

```python
import asyncio
import time
from pathlib import Path
from typing import Dict, Set, Optional, Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging

logger = logging.getLogger("file-watcher")

class CodeFileHandler(FileSystemEventHandler):
    """Handle file system events for code files"""
    
    def __init__(self, callback: Callable[[str], None]):
        self.callback = callback
        self.supported_extensions = {'.py', '.js', '.jsx', '.ts', '.tsx'}
    
    def on_modified(self, event):
        if not event.is_directory:
            path = Path(event.src_path)
            if path.suffix in self.supported_extensions:
                self.callback(str(path))
    
    def on_created(self, event):
        if not event.is_directory:
            path = Path(event.src_path)
            if path.suffix in self.supported_extensions:
                self.callback(str(path))
    
    def on_deleted(self, event):
        if not event.is_directory:
            path = Path(event.src_path)
            if path.suffix in self.supported_extensions:
                self.callback(str(path))

class FileWatcher:
    """Watch for file changes and queue updates"""
    
    def __init__(self, root_path: str, update_callback: Callable[[str], None]):
        self.root_path = Path(root_path)
        self.update_callback = update_callback
        self.observer = Observer()
        self.handler = CodeFileHandler(self._on_file_changed)
        self.is_running = False
        
        # Track pending changes with timestamps
        self.pending_changes: Dict[str, float] = {}
        self.update_delay = 60.0  # 60 seconds
        
        # Activity tracking
        self.last_activity_time = time.time()
        self.activity_timeout = 120.0  # 2 minutes of inactivity
        
    def _on_file_changed(self, file_path: str):
        """Handle file change event"""
        logger.info(f"File changed: {file_path}")
        self.pending_changes[file_path] = time.time()
        self.last_activity_time = time.time()
    
    def start(self):
        """Start watching for file changes"""
        if self.is_running:
            return
        
        self.observer.schedule(self.handler, str(self.root_path), recursive=True)
        self.observer.start()
        self.is_running = True
        
        # Start background task to process changes
        asyncio.create_task(self._process_changes())
        logger.info(f"Started file watcher for {self.root_path}")
    
    def stop(self):
        """Stop watching for file changes"""
        if not self.is_running:
            return
        
        self.observer.stop()
        self.observer.join()
        self.is_running = False
        logger.info("Stopped file watcher")
    
    async def _process_changes(self):
        """Process pending changes with debouncing"""
        while self.is_running:
            try:
                await asyncio.sleep(5.0)  # Check every 5 seconds
                
                current_time = time.time()
                ready_files = []
                
                # Find files ready for update (older than delay)
                for file_path, change_time in list(self.pending_changes.items()):
                    if current_time - change_time >= self.update_delay:
                        ready_files.append(file_path)
                        del self.pending_changes[file_path]
                
                # Check if agent is still active
                if ready_files and self._is_agent_active():
                    logger.info(f"Processing {len(ready_files)} ready files")
                    for file_path in ready_files:
                        await self.update_callback(file_path)
                
            except Exception as e:
                logger.error(f"Error in file watcher: {e}")
    
    def _is_agent_active(self) -> bool:
        """Check if coding agent is still active"""
        return time.time() - self.last_activity_time < self.activity_timeout
    
    def update_activity(self):
        """Update last activity time (called by MCP requests)"""
        self.last_activity_time = time.time()
```

**Key Features:**
- Monitors `.py`, `.js`, `.jsx`, `.ts`, `.tsx` files recursively
- Debounces changes with 60-second delay to handle chunked modifications
- Tracks activity to determine when agent is active
- Asynchronous processing to avoid blocking MCP server

### Phase 2: Activity Detection

**File: `src/activity_tracker.py`**

Track MCP server activity to detect when coding agent is active:

```python
import time
import asyncio
from typing import Optional
import logging

logger = logging.getLogger("activity-tracker")

class ActivityTracker:
    """Track MCP server activity to detect when agent is active"""
    
    def __init__(self, inactivity_timeout: float = 120.0):
        self.last_request_time = time.time()
        self.inactivity_timeout = inactivity_timeout
        self.request_count = 0
        self.active_session_start = time.time()
        
    def record_request(self, tool_name: str):
        """Record MCP tool request"""
        current_time = time.time()
        
        # Check if this is a new session
        if current_time - self.last_request_time > self.inactivity_timeout:
            self.active_session_start = current_time
            logger.info("New coding session detected")
        
        self.last_request_time = current_time
        self.request_count += 1
        
        logger.debug(f"Activity recorded: {tool_name} (total: {self.request_count})")
    
    def is_active(self) -> bool:
        """Check if agent is currently active"""
        return time.time() - self.last_request_time < self.inactivity_timeout
    
    def get_session_duration(self) -> float:
        """Get current session duration in seconds"""
        if self.is_active():
            return time.time() - self.active_session_start
        return 0.0
    
    def get_stats(self) -> dict:
        """Get activity statistics"""
        return {
            "is_active": self.is_active(),
            "last_request_time": self.last_request_time,
            "session_duration": self.get_session_duration(),
            "request_count": self.request_count,
            "inactivity_timeout": self.inactivity_timeout
        }
```

**Agent Activity Detection Logic:**
- **MCP Request Frequency**: Track time between tool calls
- **Session Detection**: New session starts after 2 minutes of inactivity
- **Request Patterns**: Rapid successive calls indicate active coding
- **Inactivity Timeout**: 2 minutes of no requests = agent inactive

### Phase 3: Incremental Index Updates

**File: `src/incremental_indexer.py`**

Handle incremental updates to the semantic index:

```python
import asyncio
import hashlib
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger("incremental-indexer")

class IncrementalIndexer:
    """Handle incremental updates to the semantic index"""
    
    def __init__(self, indexer, vector_store):
        self.indexer = indexer
        self.vector_store = vector_store
        self.file_hashes: Dict[str, str] = {}
        self.hash_file = Path("./chroma_db/file_hashes.json")
        self.load_file_hashes()
        
        # Update statistics
        self.updates_processed = 0
        self.last_update_time = None
        
    def load_file_hashes(self):
        """Load file hashes from disk"""
        if self.hash_file.exists():
            try:
                with open(self.hash_file, 'r') as f:
                    self.file_hashes = json.load(f)
                logger.info(f"Loaded {len(self.file_hashes)} file hashes")
            except Exception as e:
                logger.warning(f"Could not load file hashes: {e}")
                self.file_hashes = {}
    
    def save_file_hashes(self):
        """Save file hashes to disk"""
        try:
            self.hash_file.parent.mkdir(exist_ok=True)
            with open(self.hash_file, 'w') as f:
                json.dump(self.file_hashes, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save file hashes: {e}")
    
    def calculate_file_hash(self, file_path: str) -> Optional[str]:
        """Calculate hash of file contents"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception as e:
            logger.warning(f"Could not hash file {file_path}: {e}")
            return None
    
    async def update_file(self, file_path: str) -> dict:
        """Update index for a single file"""
        file_path = str(Path(file_path).resolve())
        
        # Check if file actually changed
        current_hash = self.calculate_file_hash(file_path)
        if current_hash is None:
            # File might have been deleted
            return await self._handle_deleted_file(file_path)
        
        previous_hash = self.file_hashes.get(file_path)
        if current_hash == previous_hash:
            logger.debug(f"File unchanged: {file_path}")
            return {"status": "unchanged", "file": file_path}
        
        logger.info(f"Updating index for: {file_path}")
        start_time = time.time()
        
        try:
            # Remove old symbols from this file
            deleted_count = self.vector_store.delete_by_file(file_path)
            
            # Add new symbols
            result = await self.indexer.update_file(file_path)
            
            # Update hash
            self.file_hashes[file_path] = current_hash
            self.save_file_hashes()
            
            # Update statistics
            self.updates_processed += 1
            self.last_update_time = time.time()
            
            update_time = time.time() - start_time
            logger.info(f"Updated {file_path} in {update_time:.2f}s: "
                       f"removed {deleted_count}, added {result.get('added', 0)}")
            
            return {
                "status": "updated",
                "file": file_path,
                "deleted": deleted_count,
                "added": result.get('added', 0),
                "update_time": update_time
            }
            
        except Exception as e:
            logger.error(f"Failed to update {file_path}: {e}")
            return {"status": "error", "file": file_path, "error": str(e)}
    
    async def _handle_deleted_file(self, file_path: str) -> dict:
        """Handle deleted file by removing from index"""
        deleted_count = self.vector_store.delete_by_file(file_path)
        
        # Remove from hash tracking
        if file_path in self.file_hashes:
            del self.file_hashes[file_path]
            self.save_file_hashes()
        
        logger.info(f"Removed {deleted_count} symbols from deleted file: {file_path}")
        
        return {
            "status": "deleted",
            "file": file_path,
            "deleted": deleted_count
        }
    
    def get_stats(self) -> dict:
        """Get incremental indexing statistics"""
        return {
            "updates_processed": self.updates_processed,
            "last_update_time": self.last_update_time,
            "tracked_files": len(self.file_hashes),
            "hash_file_size": self.hash_file.stat().st_size if self.hash_file.exists() else 0
        }
```

**Hash-Based Change Detection:**
- SHA256 hashes of file contents stored in `./chroma_db/file_hashes.json`
- Only update files with actual content changes
- Handle file deletions by removing from index
- Persistent hash storage survives server restarts

### Phase 4: MCP Server Integration

**File: `src/server.py` (modifications)**

Integration with existing MCP server:

```python
# Add imports at the top
from .file_watcher import FileWatcher
from .activity_tracker import ActivityTracker
from .incremental_indexer import IncrementalIndexer

# Add after semantic search initialization
activity_tracker = ActivityTracker()
file_watcher = None
incremental_indexer = None

# Initialize file watcher if semantic search is available
if semantic_available:
    incremental_indexer = IncrementalIndexer(
        semantic_searcher['indexer'],
        semantic_searcher['vector_store']
    )
    
    async def handle_file_update(file_path: str):
        """Handle file update from watcher"""
        await incremental_indexer.update_file(file_path)
    
    file_watcher = FileWatcher(".", handle_file_update)
    file_watcher.start()
    logger.info("Started incremental indexing with file watcher")

# Add activity tracking to all tool handlers
@app.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool calls"""
    # Record activity
    activity_tracker.record_request(name)
    
    # Update file watcher activity
    if file_watcher:
        file_watcher.update_activity()
    
    # ... rest of existing code ...
```

**Integration Points:**
- Initialize components when semantic search is available
- Track activity on every MCP tool call
- Update file watcher activity to keep it synchronized
- Graceful handling when semantic search is not available

### Phase 5: Monitoring and Control Tools

**New MCP Tools:**

```python
@app.tool()
async def get_incremental_indexing_status() -> Dict:
    """Get status of incremental indexing system"""
    
    if not incremental_indexer:
        return {"error": "Incremental indexing not available"}
    
    stats = incremental_indexer.get_stats()
    activity_stats = activity_tracker.get_stats()
    
    return {
        "incremental_indexing": {
            "enabled": True,
            "updates_processed": stats["updates_processed"],
            "last_update": stats["last_update_time"],
            "tracked_files": stats["tracked_files"]
        },
        "file_watcher": {
            "active": file_watcher.is_running if file_watcher else False,
            "pending_changes": len(file_watcher.pending_changes) if file_watcher else 0,
            "update_delay": file_watcher.update_delay if file_watcher else 0
        },
        "activity_tracker": activity_stats
    }

@app.tool()
async def force_incremental_update(file_paths: Optional[List[str]] = None) -> Dict:
    """Force incremental update of specific files or all changed files"""
    
    if not incremental_indexer:
        return {"error": "Incremental indexing not available"}
    
    results = []
    
    if file_paths:
        # Update specific files
        for file_path in file_paths:
            result = await incremental_indexer.update_file(file_path)
            results.append(result)
    else:
        # Update all pending changes
        if file_watcher:
            pending_files = list(file_watcher.pending_changes.keys())
            for file_path in pending_files:
                result = await incremental_indexer.update_file(file_path)
                results.append(result)
                # Remove from pending
                if file_path in file_watcher.pending_changes:
                    del file_watcher.pending_changes[file_path]
    
    return {
        "forced_updates": len(results),
        "results": results
    }
```

## Update Triggering Logic

### Agent Activity Detection

The system knows the coding agent is still running through multiple signals:

1. **MCP Request Frequency**: Active agents make frequent tool calls
2. **Session Detection**: New session starts after 2 minutes of inactivity
3. **Request Patterns**: Rapid successive calls indicate active coding
4. **Heartbeat Updates**: Every MCP call updates the activity tracker

### Update Decision Algorithm

```python
def should_trigger_update(self) -> bool:
    """Determine if updates should be triggered"""
    return (
        self.has_pending_changes() and
        self.oldest_change_age() > self.update_delay and
        self.activity_tracker.is_active()
    )
```

**Conditions for Update:**
- Files have pending changes
- Oldest change is >60 seconds old (debounce period)
- Agent is currently active (recent MCP requests)

### Chunked Change Handling

The 60-second debounce period accounts for how coding agents work:

1. **Agent makes multiple related changes** (imports, functions, tests)
2. **File system events fire rapidly** for each change
3. **System queues all changes** with timestamps
4. **After 60 seconds of stability**, changes are processed
5. **Only if agent is still active** (recent MCP requests)

## Configuration

### Tunable Parameters

```python
# File watcher configuration
UPDATE_DELAY = 60.0        # Wait 60s after last change before updating
INACTIVITY_TIMEOUT = 120.0 # Agent inactive after 2 minutes of no requests
CHECK_INTERVAL = 5.0       # Check for ready updates every 5 seconds

# Supported file extensions
SUPPORTED_EXTENSIONS = {'.py', '.js', '.jsx', '.ts', '.tsx'}

# Activity tracking
SESSION_TIMEOUT = 120.0    # New session after 2 minutes inactivity
```

### Storage Locations

- **File hashes**: `./chroma_db/file_hashes.json`
- **Vector index**: `./chroma_db/` (existing)
- **Logs**: Standard logging output

## Benefits

1. **Always Current**: Index stays up-to-date with code changes
2. **Efficient**: Only reindex changed files, not entire codebase
3. **Smart Timing**: Waits for agents to finish chunked changes
4. **Non-Intrusive**: Updates happen in background during active sessions
5. **Resilient**: Handles file deletions, moves, and edge cases
6. **Monitorable**: Status and control tools for debugging

## Dependencies

### New Dependencies

Add to `requirements.txt`:
```
watchdog>=3.0.0  # File system monitoring
```

### Import Dependencies

- `asyncio` - Async processing
- `hashlib` - File change detection
- `json` - Hash persistence
- `pathlib` - File path handling
- `time` - Timestamp management
- `logging` - Debug and monitoring

## Rollout Strategy

### Phase 1: Core Infrastructure (Week 1)
- Implement `FileWatcher` class
- Implement `ActivityTracker` class
- Basic file change detection

### Phase 2: Incremental Updates (Week 2)
- Implement `IncrementalIndexer` class
- Hash-based change detection
- File deletion handling

### Phase 3: Integration (Week 3)
- Integrate with MCP server
- Activity tracking on tool calls
- Error handling and logging

### Phase 4: Monitoring (Week 4)
- Status and control MCP tools
- Performance monitoring
- Documentation and testing

### Phase 5: Optimization (Week 5)
- Performance tuning
- Configuration options
- Advanced features (batch updates, etc.)

## Testing Strategy

### Unit Tests
- File change detection accuracy
- Hash calculation consistency
- Activity tracking logic
- Update triggering conditions

### Integration Tests
- End-to-end file change to index update
- Agent activity simulation
- Error recovery scenarios
- Performance under load

### Manual Testing
- Real coding session simulation
- Multiple file changes
- Edge cases (file deletions, renames)
- Long-running sessions

## Success Metrics

1. **Accuracy**: Index reflects current code state within 60 seconds
2. **Performance**: <2 seconds per file update
3. **Reliability**: Handles edge cases without crashes
4. **Efficiency**: Only updates changed files
5. **Usability**: Works transparently in background

This plan provides a comprehensive approach to incremental indexing that respects agent workflows while maintaining fresh semantic search results.