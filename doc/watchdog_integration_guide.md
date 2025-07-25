# Watchdog Integration Guide

This guide covers how to use the watchdog file monitor with the enhanced ignore system in MCP-RageX.

## Overview

The watchdog integration enables automatic hot reloading of `.mcpignore` files when they change. This is particularly useful for:
- Development environments where ignore patterns change frequently
- CI/CD pipelines that need to react to configuration changes
- IDE integrations that update ignore patterns dynamically

## Installation

Install the optional watchdog dependency:

```bash
# Using uv (recommended)
uv pip install watchdog

# Or using pip
pip install watchdog
```

## Basic Usage

### Simple Monitoring

```python
from src.ignore import IgnoreManager
from src.watchdog_monitor import WatchdogMonitor

# Create ignore manager
ignore_manager = IgnoreManager("/path/to/project")

# Create and start monitor
monitor = WatchdogMonitor(ignore_manager)
monitor.start()

# Files are automatically reloaded when .mcpignore changes
# ... your code here ...

# Stop when done
monitor.stop()
```

### With Change Callbacks

```python
def on_ignore_change(file_path):
    print(f"Ignore file changed: {file_path}")
    # React to changes (e.g., restart indexing)

monitor.start(on_change_callback=on_ignore_change)
```

### Context Manager Usage

```python
with WatchdogMonitor(ignore_manager) as monitor:
    # Monitor is active within this block
    process_files()
# Monitor automatically stops
```

## Advanced Features

### Threaded Monitoring

Run the monitor in a background thread:

```python
from src.watchdog_monitor import ThreadedWatchdogMonitor

monitor = ThreadedWatchdogMonitor(ignore_manager)
monitor.start_threaded()

# Do other work while monitor runs in background
perform_long_operation()

monitor.stop_threaded()
```

### Custom Debouncing

Prevent rapid reloads with custom debounce settings:

```python
# Wait at least 2 seconds between reloads
monitor = WatchdogMonitor(
    ignore_manager,
    debounce_seconds=2.0
)
```

### Multi-Path Monitoring

Monitor multiple directories:

```python
monitor.start(paths=[
    "/path/to/project",
    "/path/to/shared/configs",
    "/home/user/.config/ragex"
])

# Add paths dynamically
monitor.add_path("/another/path")
```

## Ignore-Aware File Processing

Create file processors that automatically respect ignore rules:

```python
from watchdog.events import FileSystemEventHandler
from src.watchdog_monitor import create_ignore_aware_handler

# Create base handler class
IgnoreAwareHandler = create_ignore_aware_handler(ignore_manager)

class CodeProcessor(IgnoreAwareHandler):
    def on_created(self, event):
        if not event.is_directory:
            print(f"New code file: {event.src_path}")
            # Process only non-ignored files
            
    def on_modified(self, event):
        if not event.is_directory:
            print(f"Code changed: {event.src_path}")
            # Re-index or analyze the file

# Use with watchdog observer
from watchdog.observers import Observer

observer = Observer()
observer.schedule(CodeProcessor(), "/path/to/project", recursive=True)
observer.start()
```

## Integration with MCP Server

### Option 1: Server-Level Integration

Add watchdog monitoring to your MCP server:

```python
# In server.py or similar
class MCPServer:
    def __init__(self):
        self.ignore_manager = IgnoreManager(self.root_path)
        self.watchdog_monitor = None
        
    def start(self):
        # Start watchdog monitoring
        if self.enable_hot_reload:
            self.watchdog_monitor = WatchdogMonitor(self.ignore_manager)
            self.watchdog_monitor.start(
                on_change_callback=self.on_ignore_change
            )
            
    def on_ignore_change(self, file_path):
        logger.info(f"Reloaded ignore patterns from: {file_path}")
        # Optionally notify clients or update caches
        
    def stop(self):
        if self.watchdog_monitor:
            self.watchdog_monitor.stop()
```

### Option 2: Pattern Matcher Integration

The `PatternMatcher` class already supports hot reloading:

```python
from src.pattern_matcher import PatternMatcher

matcher = PatternMatcher()

# Enable watchdog monitoring (future implementation)
# matcher.enable_hot_reload()

# Or manually notify of changes
matcher.notify_file_changed("/path/to/.mcpignore")
```

## Configuration

### Environment Variables

```bash
# Control ignore file warnings
export RAGEX_IGNOREFILE_WARNING=false

# Set custom ignore filename (future)
export RAGEX_IGNORE_FILENAME=.ragexignore
```

### Programmatic Configuration

```python
# Custom configuration
monitor = WatchdogMonitor(
    ignore_manager,
    recursive=True,          # Watch subdirectories
    debounce_seconds=1.0    # Debounce period
)

# Check status
if monitor.is_running():
    paths = monitor.get_watched_paths()
    print(f"Watching: {paths}")
```

## Performance Considerations

1. **Debouncing**: Set appropriate debounce periods to prevent excessive reloads
2. **Path Scope**: Limit watched paths to relevant directories
3. **Resource Usage**: Each watched directory consumes system resources
4. **Large Projects**: Consider watching only configuration directories

## Troubleshooting

### Common Issues

1. **Import Error**: Ensure watchdog is installed
   ```bash
   uv pip install watchdog
   ```

2. **Permission Denied**: Check file system permissions
   ```bash
   ls -la .mcpignore
   ```

3. **Changes Not Detected**: Verify the monitor is running
   ```python
   print(f"Monitor running: {monitor.is_running()}")
   ```

### Debug Logging

Enable debug logging to see detailed activity:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("watchdog-monitor")
```

## Examples

See `examples/watchdog_example.py` for complete working examples:

```bash
# Run interactive examples
uv run python examples/watchdog_example.py
```

Available examples:
1. Basic monitoring
2. Threaded monitoring
3. Ignore-aware file processing
4. Context manager usage

## Future Enhancements

Planned improvements:
- Automatic enable/disable based on environment
- Integration with VS Code and other IDEs
- Network-based change notifications
- Pattern validation on reload
- Change history and rollback