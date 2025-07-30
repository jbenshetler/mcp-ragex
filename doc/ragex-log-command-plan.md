# RageX Log Command Implementation Plan

## Overview

Add a comprehensive logging system to ragex that allows users to view logs at both global and per-project levels, with real-time following capabilities similar to `docker logs` and `tail -f`.

## Current State Analysis

### Existing Logging Infrastructure
- **Docker containers** generate logs automatically (stdout/stderr)
- **Socket daemon** uses Python logging with structured output
- **Search operations** produce output but no persistent logging
- **Indexing operations** show progress but no retained logs
- **No centralized log aggregation** currently exists

### Current Log Sources
1. **Daemon containers** - Socket daemon startup, command processing, errors
2. **Direct command execution** - Index operations, search results, errors
3. **Wrapper script** - Debug output (when RAGEX_DEBUG=true)
4. **Docker operations** - Container lifecycle, volume management

## Proposed Implementation

### 1. Command Interface Design

```bash
# Global logs (all ragex activity for current user)
ragex log                           # Show recent global logs
ragex log -f                        # Follow global logs
ragex log --tail 100               # Show last 100 lines
ragex log --since "2024-01-15"     # Show logs since date

# Per-project logs
ragex log <project_id>              # Show recent logs for specific project
ragex log <project_id> -f           # Follow logs for specific project
ragex log mcp-ragex -f              # Follow by project name (if unique)

# Combined options
ragex log <project_id> --tail 50 -f # Show last 50 lines then follow
ragex log --level error             # Filter by log level
ragex log --grep "search"           # Filter by content
```

### 2. Log Storage Architecture

#### Option A: Centralized Log Files (Recommended)
```
/data/logs/
├── global.log                     # All ragex activity
├── projects/
│   ├── ragex_1000_8375a7fda539e891.log
│   ├── ragex_1000_266b9bcd293ce8af.log
│   └── admin.log
└── archive/                       # Rotated logs
    ├── global.log.1
    └── projects/
```

#### Option B: Docker Logs Integration
- Use `docker logs` for daemon containers
- Aggregate direct command logs separately
- More complex but leverages existing Docker infrastructure

### 3. Log Format Standardization

**Structured Log Format:**
```
2024-01-15 14:22:30.123 [INFO] [project:mcp-ragex] [command:search] Query: "function auth"
2024-01-15 14:22:30.456 [DEBUG] [project:mcp-ragex] [daemon] Socket connection established
2024-01-15 14:22:31.789 [ERROR] [project:docker-test] [index] Failed to process file: syntax error
```

**Fields:**
- **Timestamp** - ISO format with milliseconds
- **Level** - INFO, DEBUG, WARN, ERROR
- **Project** - Project name or ID
- **Component** - daemon, index, search, wrapper
- **Message** - Human-readable content

### 4. Implementation Components

#### A. Enhanced Logging Infrastructure

**1. Centralized Logger Module (`src/lib/logger.py`)**
```python
class RagexLogger:
    def __init__(self, project_id: str = None):
        self.project_id = project_id
        self.global_handler = self._setup_global_handler()
        self.project_handler = self._setup_project_handler() if project_id else None
    
    def log(self, level: str, component: str, message: str, **kwargs):
        # Write to both global and project-specific logs
        pass
    
    def _setup_global_handler(self):
        # Configure global log file handler
        pass
```

**2. Docker Volume Log Persistence**
- Mount `/data/logs` volume for persistent log storage
- Ensure proper permissions for log file access
- Implement log rotation to prevent disk bloat

**3. Enhanced Daemon Logging**
```python
# In socket_daemon.py
logger = RagexLogger(project_id=os.environ.get('PROJECT_NAME'))

async def handle_request(self, reader, writer):
    logger.log('INFO', 'daemon', f'Handling command: {command}', 
               client=addr, command=command)
```

#### B. Log Command Implementation

**1. Entrypoint Handler (`docker/entrypoint.sh`)**
```bash
"log")
    shift
    project_id=""
    follow=false
    tail_lines=""
    since=""
    level=""
    grep_pattern=""
    
    # Parse arguments
    while [ $# -gt 0 ]; do
        case "$1" in
            -f|--follow) follow=true; shift ;;
            --tail) tail_lines="$2"; shift 2 ;;
            --since) since="$2"; shift 2 ;;
            --level) level="$2"; shift 2 ;;
            --grep) grep_pattern="$2"; shift 2 ;;
            -*) echo "Unknown option: $1"; exit 1 ;;
            *) project_id="$1"; shift ;;
        esac
    done
    
    exec python -m src.cli.log --project "$project_id" \
         ${follow:+--follow} \
         ${tail_lines:+--tail "$tail_lines"} \
         ${since:+--since "$since"} \
         ${level:+--level "$level"} \
         ${grep_pattern:+--grep "$grep_pattern"}
    ;;
```

**2. Log CLI Module (`src/cli/log.py`)**
```python
import argparse
import asyncio
from pathlib import Path
from typing import Optional

class LogViewer:
    def __init__(self, project_id: Optional[str] = None):
        self.project_id = project_id
        self.log_dir = Path('/data/logs')
    
    async def show_logs(self, follow: bool = False, tail: int = None, 
                       since: str = None, level: str = None, 
                       grep_pattern: str = None):
        # Implementation for log viewing
        pass
    
    def _get_log_files(self) -> List[Path]:
        if self.project_id:
            return [self.log_dir / 'projects' / f'{self.project_id}.log']
        else:
            return [self.log_dir / 'global.log']
```

**3. Wrapper Script Integration (`ragex`)**
```bash
case "$COMMAND" in
    "list-projects"|"ls"|"clean-project"|"rm"|"register"|"unregister"|"log")
        # Commands that don't need workspace but may need daemon access
        # ...existing logic...
        ;;
```

#### C. Log Integration Points

**1. Command Execution Logging**
- **Index operations** - Log start, progress, completion, errors
- **Search operations** - Log queries, results count, performance
- **Daemon lifecycle** - Log startup, shutdown, crashes
- **Registration** - Log MCP registration/unregistration events

**2. Error Tracking**
- **Failed commands** - Capture stderr and exit codes
- **Docker issues** - Container start failures, volume problems
- **Permission errors** - File access, socket connection issues

**3. Performance Metrics**
- **Search timing** - Query execution time, result processing
- **Index statistics** - Files processed, symbols extracted, time taken
- **Daemon performance** - Command processing time, memory usage

### 5. Advanced Features

#### A. Log Rotation and Management
```bash
# Automatic log rotation when files exceed size
# Keep last N rotated files
# Compress old logs to save space
ragex log --clean --older-than 30d  # Clean logs older than 30 days
ragex log --rotate                  # Force log rotation
```

#### B. Log Analysis and Filtering
```bash
ragex log --stats                   # Show log statistics
ragex log --errors-only             # Show only errors
ragex log --performance             # Show performance metrics
ragex log --json                    # Output structured JSON logs
```

#### C. Multi-Project Log Aggregation
```bash
ragex log --all-projects            # Show logs from all projects
ragex log --projects proj1,proj2    # Show logs from specific projects
```

### 6. User Experience Considerations

#### A. Project Name Resolution
- Allow using project names instead of IDs: `ragex log mcp-ragex`
- **Uniqueness validation** - Check that project name maps to exactly one project
- **Clear error messages** when project names are ambiguous or not found
- Auto-complete project names from available projects
- Fuzzy matching for partial project names (only when unique)

#### B. Output Formatting
- **Colorized output** - Different colors for log levels
- **Compact mode** - Shorter format for following logs
- **Timestamp options** - Relative times, UTC, local timezone

#### C. Integration with External Tools
- **Pipe-friendly output** - Clean format for grep, awk, etc.
- **JSON export** - Structured data for analysis tools
- **Syslog integration** - Optional forwarding to system logs

### 7. Implementation Phases

#### Phase 1: Basic Log Command (High Priority)
1. Add basic log command to entrypoint.sh
2. Implement simple file-based logging in daemon
3. Create log viewing functionality with -f flag
4. Support per-project and global log viewing
5. Add command to ragex wrapper script

#### Phase 2: Enhanced Logging Infrastructure (Medium Priority)
1. Implement structured logging format
2. Add log rotation and management
3. Integrate logging into all command operations
4. Add filtering and search capabilities

#### Phase 3: Advanced Features (Low Priority)
1. Add performance metrics and statistics
2. Implement log analysis tools
3. Add external integrations (syslog, JSON export)
4. Create log cleanup and archival features

### 8. Project Name Resolution Implementation

#### A. Project Resolution Logic (`src/lib/project_resolver.py`)
```python
class ProjectResolver:
    def __init__(self, projects_dir: Path = Path('/data/projects')):
        self.projects_dir = projects_dir
    
    def resolve_project_identifier(self, identifier: str) -> str:
        """
        Resolve a project identifier (name or ID) to a unique project ID.
        
        Args:
            identifier: Project name or project ID
            
        Returns:
            Project ID if unique match found
            
        Raises:
            ProjectNotFoundError: No projects match the identifier
            AmbiguousProjectError: Multiple projects match the identifier
        """
        # First, check if it's already a valid project ID
        if self._is_valid_project_id(identifier):
            return identifier
        
        # Search by project name
        matches = self._find_projects_by_name(identifier)
        
        if len(matches) == 0:
            raise ProjectNotFoundError(f"No project found with name '{identifier}'")
        elif len(matches) == 1:
            return matches[0]
        else:
            raise AmbiguousProjectError(
                f"Multiple projects found with name '{identifier}': "
                f"{', '.join(matches)}"
            )
    
    def _find_projects_by_name(self, name: str) -> List[str]:
        """Find all project IDs that have the given display name"""
        matches = []
        
        for project_dir in self.projects_dir.glob('*/'):
            project_id = project_dir.name
            info_file = project_dir / 'project_info.json'
            
            if info_file.exists():
                try:
                    info = json.loads(info_file.read_text())
                    workspace_basename = info.get('workspace_basename', '')
                    workspace_path = info.get('workspace_path', '')
                    
                    # Check basename match
                    if workspace_basename == name:
                        matches.append(project_id)
                    # Also check path basename for old projects
                    elif workspace_path != 'unknown':
                        path_basename = Path(workspace_path).name
                        if path_basename == name:
                            matches.append(project_id)
                            
                except (json.JSONDecodeError, OSError):
                    continue
        
        return matches

class ProjectNotFoundError(Exception):
    pass

class AmbiguousProjectError(Exception):
    pass
```

#### B. Error Message Examples
```bash
# Project not found
$ ragex log nonexistent-project
❌ Error: No project found with name 'nonexistent-project'

Available projects:
  mcp-ragex [ragex_1000_8375a7fda539e891]
  docker-test [ragex_1000_6def3fc82d5eae70] 
  nancyknows-web [ragex_1000_51205200142a978e]

# Ambiguous project name
$ ragex log test-project
❌ Error: Multiple projects found with name 'test-project':
  ragex_1000_abc123def456 (/home/jeff/projects/test-project)
  ragex_1000_789xyz012345 (/home/jeff/other/test-project)

Use the full project ID instead:
  ragex log ragex_1000_abc123def456
  ragex log ragex_1000_789xyz012345

# Successful resolution
$ ragex log mcp-ragex -f
📋 Following logs for project: mcp-ragex [ragex_1000_8375a7fda539e891]
2024-01-15 14:22:30.123 [INFO] [search] Query: "function auth"
...
```

#### C. Command Line Integration
```bash
# In entrypoint.sh log command handler
"log")
    shift
    project_identifier=""
    # ... other argument parsing ...
    
    # Handle project identifier
    if [ $# -gt 0 ]; then
        case "$1" in
            -*) ;;  # It's a flag, not a project identifier
            *) project_identifier="$1"; shift ;;
        esac
    fi
    
    # Resolve project identifier if provided
    if [ -n "$project_identifier" ]; then
        # Use Python to resolve the identifier
        resolved_id=$(python -c "
from src.lib.project_resolver import ProjectResolver
resolver = ProjectResolver()
try:
    print(resolver.resolve_project_identifier('$project_identifier'))
except Exception as e:
    print(f'ERROR: {e}', file=sys.stderr)
    sys.exit(1)
")
        if [ $? -ne 0 ]; then
            exit 1  # Error message already printed by Python
        fi
        project_id="$resolved_id"
    fi
    
    exec python -m src.cli.log --project "$project_id" \
         ${follow:+--follow} \
         # ... other options ...
```

### 9. Technical Implementation Details

#### A. File Watching Implementation
```python
# Use inotify (Linux) or polling for log following
import select
import os

def follow_log_file(filepath: Path, callback):
    with open(filepath, 'r') as f:
        # Seek to end
        f.seek(0, 2)
        
        while True:
            line = f.readline()
            if line:
                callback(line.rstrip())
            else:
                # Wait for new data
                time.sleep(0.1)
```

#### B. Log Aggregation Strategy
```python
def get_aggregated_logs(project_id: Optional[str] = None, 
                       since: datetime = None) -> Iterator[LogEntry]:
    sources = []
    
    if project_id:
        # Single project logs
        sources.append(f'/data/logs/projects/{project_id}.log')
    else:
        # Global logs from all sources
        sources.extend(glob.glob('/data/logs/projects/*.log'))
        sources.append('/data/logs/global.log')
    
    # Merge and sort by timestamp
    return merge_log_streams(sources, since)
```

#### C. Docker Integration
```bash
# For daemon logs, also integrate with docker logs
if is_daemon_running; then
    docker logs "${DAEMON_CONTAINER_NAME}" 2>&1 | \
        while read line; do
            echo "$(date -Iseconds) [DOCKER] [daemon] $line"
        done
fi
```

### 9. Configuration Options

#### A. Environment Variables
- `RAGEX_LOG_LEVEL` - Default log level (DEBUG, INFO, WARN, ERROR)
- `RAGEX_LOG_FORMAT` - Output format (text, json, compact)
- `RAGEX_LOG_MAX_SIZE` - Maximum log file size before rotation
- `RAGEX_LOG_MAX_FILES` - Number of rotated log files to keep

#### B. Per-Project Configuration
```json
// In project_info.json
{
    "logging": {
        "level": "INFO",
        "retain_days": 30,
        "performance_tracking": true
    }
}
```

### 10. Error Handling and Edge Cases

#### A. Missing Log Files
- Handle cases where log files don't exist yet
- Create log directories on demand
- Graceful fallback when log files are locked

#### B. Permission Issues
- Ensure proper Docker volume permissions
- Handle cases where log directory is not writable
- Provide clear error messages for permission problems

#### C. Large Log Files
- Implement efficient tail operations for large files
- Prevent memory issues when following very active logs
- Provide warnings for extremely large log files

### 11. Testing Strategy

#### A. Unit Tests
- Test log parsing and filtering
- Test file watching mechanisms
- Test project ID resolution

#### B. Integration Tests
- Test log command with real daemon operations
- Test log following during active operations
- Test log rotation and cleanup

#### C. Performance Tests
- Test log viewing with large log files
- Test following performance under high load
- Test memory usage during extended following

### 12. Documentation Requirements

#### A. User Documentation
- Add log command to ragex help text
- Create examples for common log viewing scenarios
- Document log format and filtering options

#### B. Developer Documentation
- Document logging API for adding new log sources
- Explain log file structure and rotation
- Provide troubleshooting guide for log issues

## Success Criteria

1. **Core Functionality**
   - `ragex log` shows recent global activity
   - `ragex log <project_id>` shows project-specific logs
   - `ragex log -f` provides real-time log following
   - Log output is clean and parseable

2. **User Experience**
   - Commands are intuitive and follow Unix conventions
   - Project names can be used instead of IDs when unambiguous
   - Log output is colorized and well-formatted
   - Performance is acceptable even with large log files

3. **System Integration**
   - Logs persist across container restarts
   - Log rotation prevents disk space issues
   - Integration with existing ragex commands is seamless
   - Error conditions are handled gracefully

4. **Maintainability**
   - Logging infrastructure is extensible for new components
   - Log format is structured and searchable
   - Configuration options provide flexibility
   - Code is well-tested and documented

## Alternative Approaches Considered

### 1. Docker Logs Only
**Pros:** Leverages existing Docker infrastructure
**Cons:** Limited to daemon containers, no aggregation across direct commands

### 2. Syslog Integration
**Pros:** Uses system logging infrastructure
**Cons:** More complex setup, less portable across systems

### 3. Database-Based Logging
**Pros:** Rich querying capabilities, structured storage
**Cons:** Additional dependency, overkill for current needs

### 4. External Log Management (ELK, etc.)
**Pros:** Professional-grade log analysis
**Cons:** Too complex for a developer tool, requires additional infrastructure

## Conclusion

The proposed file-based logging system with centralized log aggregation provides the best balance of functionality, simplicity, and maintainability for ragex. The phased implementation approach allows for incremental delivery of value while keeping the scope manageable.

The key innovation is providing both global and per-project log views while maintaining the simplicity and directness that ragex users expect. The `-f` following capability makes it easy to debug issues in real-time, similar to familiar tools like `tail -f` and `docker logs -f`.