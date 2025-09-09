# RAGex Init Command Implementation Plan

## Current Indexing Approach Analysis

### Current Flow
1. **`ragex start` or `ragex index`** → Synchronous blocking operation
2. **Daemon startup:** Container starts if not running
3. **Indexing execution:** `smart_index.py` runs and blocks until complete
4. **User feedback:** Progress bars and completion messages shown
5. **Return:** Command returns only after indexing completes

### Current Architecture
```
ragex CLI → exec_via_daemon() → socket_client.py → socket_daemon.py → smart_index.py
    ↓               ↓                 ↓                 ↓                ↓
 Blocks CLI    Starts daemon    Sends command    Executes sync    Blocks until done
```

### Current Behavior
- **Always synchronous:** User waits for full indexing completion
- **Immediate feedback:** Progress bars, file counts, completion time
- **Error handling:** Immediate failure feedback
- **Resource visibility:** User sees exactly what's happening

## Proposed `ragex init` Command

### Command Interface
```bash
# Async mode (default) - Start daemon, trigger indexing, return immediately
ragex init [path] [--name PROJECT_NAME]

# Sync mode - Block until indexing completes (current behavior)
ragex init [path] [--name PROJECT_NAME] --sync

# Other options
ragex init --help                    # Show help
ragex init --status                  # Check if init is in progress
ragex init --cancel                  # Cancel running background indexing
```

### Proposed Flow Architecture

#### Async Mode (Default)
```
ragex init → Start daemon → Trigger background indexing → Return immediately
     ↓              ↓                    ↓                      ↓
  Quick CLI    Daemon starts     Background worker         User can continue
  response      in background        indexing             working immediately
```

#### Sync Mode (`--sync`)
```
ragex init --sync → Start daemon → Block on indexing → Return when complete
         ↓               ↓               ↓                     ↓
    Current behavior  Same as now    User waits           Same as ragex start
```

## Key Differences from Current Approach

### 1. **User Experience**
| Aspect | Current (`ragex start`) | Proposed (`ragex init`) | Proposed (`ragex init --sync`) |
|--------|------------------------|-------------------------|-------------------------------|
| **CLI Blocking** | ✅ Blocks until done | ❌ Returns immediately | ✅ Blocks until done |
| **Progress Feedback** | ✅ Real-time progress bars | ❌ Background, no direct feedback | ✅ Real-time progress bars |
| **Error Feedback** | ✅ Immediate errors | ⚠️ Delayed/logged errors | ✅ Immediate errors |
| **User Workflow** | Must wait for indexing | Can continue working | Must wait for indexing |

### 2. **Daemon Management**
| Aspect | Current | Async Init | Sync Init |
|--------|---------|------------|-----------|
| **Daemon Lifecycle** | Starts → Indexes → Stays running | Starts → Returns → Indexes in background | Starts → Indexes → Stays running |
| **Process Management** | Daemon handles sync execution | Daemon manages background workers | Same as current |
| **Resource Usage** | Single indexing process | Background worker process | Same as current |

### 3. **Status Visibility**
| Aspect | Current | Async Init | Sync Init |
|--------|---------|------------|-----------|
| **Index Status** | Known immediately | Requires status check | Known immediately |
| **Progress Tracking** | CLI progress bars | Daemon logs only | CLI progress bars |
| **Completion Notification** | CLI return code | Background completion | CLI return code |

### 4. **Error Handling**
| Aspect | Current | Async Init | Sync Init |
|--------|---------|------------|-----------|
| **Error Detection** | Immediate CLI failure | Background failure in logs | Immediate CLI failure |
| **Recovery** | User can retry immediately | May need status check first | User can retry immediately |
| **Debugging** | Clear error output | Errors in daemon logs | Clear error output |

## Implementation Design

### Phase 1: CLI Command Interface

#### Add `init` Command to CLI
**File:** `ragex` (Python CLI script)

```python
# Add to argument parser
init_parser = subparsers.add_parser('init',
    help='Initialize project (start daemon and index)')
init_parser.add_argument('path', nargs='?', default='.',
    help='Path to index (default: current directory)')
init_parser.add_argument('--name',
    help='Custom name for the project')
init_parser.add_argument('--sync', action='store_true',
    help='Block until indexing completes (default: async)')
init_parser.add_argument('--status', action='store_true',
    help='Check initialization status')
init_parser.add_argument('--cancel', action='store_true',
    help='Cancel background initialization')

def cmd_init(self, args: argparse.Namespace) -> int:
    """Handle init command"""
    if args.status:
        return self.init_status()
    elif args.cancel:
        return self.init_cancel()
    elif args.sync:
        return self.init_sync(args)
    else:
        return self.init_async(args)
```

#### Implementation Methods
```python
def init_async(self, args: argparse.Namespace) -> int:
    """Start daemon and trigger background indexing"""
    print(f"🚀 Initializing {self.workspace_path}")
    
    # Start daemon if not running
    if not self.is_daemon_running():
        if not self.start_daemon():
            return 1
    
    # Trigger background indexing
    cmd_args = [args.path]
    if args.name:
        cmd_args.extend(['--name', args.name])
    
    result = self.exec_via_daemon('init_async', cmd_args, use_tty=False)
    
    if result == 0:
        print("✅ Initialization started in background")
        print("📊 Check status with: ragex init --status")
        print("🔍 View logs with: ragex log -f")
    
    return result

def init_sync(self, args: argparse.Namespace) -> int:
    """Synchronous initialization (same as current behavior)"""
    # This is identical to current ragex start/index behavior
    return self.cmd_index(args)

def init_status(self) -> int:
    """Check initialization status"""
    if not self.is_daemon_running():
        print("❌ Daemon not running")
        return 1
    
    # Query daemon for indexing status
    result = self.exec_via_daemon('init_status', [], use_tty=False)
    return result

def init_cancel(self) -> int:
    """Cancel background initialization"""
    if not self.is_daemon_running():
        print("❌ Daemon not running")
        return 1
    
    result = self.exec_via_daemon('init_cancel', [], use_tty=False)
    return result
```

### Phase 2: Daemon Background Processing

#### Socket Daemon Updates
**File:** `src/socket_daemon.py`

```python
class SocketDaemon:
    def __init__(self):
        # ... existing init ...
        self.background_tasks = {}  # Track background operations
        self.task_counter = 0
    
    async def handle_init_async(self, args: List[str]) -> Dict[str, Any]:
        """Start background indexing task"""
        try:
            # Create background task
            task_id = f"init_{self.task_counter}"
            self.task_counter += 1
            
            # Start indexing in background
            task = asyncio.create_task(
                self._background_index(task_id, args)
            )
            self.background_tasks[task_id] = {
                'task': task,
                'type': 'init',
                'started_at': datetime.now(),
                'status': 'running'
            }
            
            return {
                'success': True,
                'task_id': task_id,
                'message': 'Background indexing started'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def handle_init_status(self, args: List[str]) -> Dict[str, Any]:
        """Check status of background tasks"""
        active_tasks = {k: v for k, v in self.background_tasks.items() 
                       if not v['task'].done()}
        
        if not active_tasks:
            return {
                'success': True,
                'status': 'idle',
                'message': 'No background initialization running'
            }
        
        # Return status of active tasks
        status_info = []
        for task_id, task_info in active_tasks.items():
            status_info.append({
                'task_id': task_id,
                'type': task_info['type'],
                'status': task_info['status'],
                'started_at': task_info['started_at'].isoformat()
            })
        
        return {
            'success': True,
            'status': 'running',
            'tasks': status_info
        }
    
    async def handle_init_cancel(self, args: List[str]) -> Dict[str, Any]:
        """Cancel background initialization"""
        cancelled_count = 0
        for task_id, task_info in self.background_tasks.items():
            if not task_info['task'].done():
                task_info['task'].cancel()
                task_info['status'] = 'cancelled'
                cancelled_count += 1
        
        return {
            'success': True,
            'cancelled': cancelled_count,
            'message': f'Cancelled {cancelled_count} background tasks'
        }
    
    async def _background_index(self, task_id: str, args: List[str]):
        """Execute indexing in background"""
        try:
            # Update task status
            self.background_tasks[task_id]['status'] = 'indexing'
            
            # Execute the same indexing logic as smart_index.py
            # but capture output to logs instead of stdout
            result = await self._run_smart_index(args, background=True)
            
            # Update task status
            self.background_tasks[task_id]['status'] = 'completed'
            self.background_tasks[task_id]['result'] = result
            
            logger.info(f"Background indexing {task_id} completed successfully")
            
        except asyncio.CancelledError:
            self.background_tasks[task_id]['status'] = 'cancelled'
            logger.info(f"Background indexing {task_id} was cancelled")
            
        except Exception as e:
            self.background_tasks[task_id]['status'] = 'failed'
            self.background_tasks[task_id]['error'] = str(e)
            logger.error(f"Background indexing {task_id} failed: {e}")
```

#### Smart Index Updates
**File:** `scripts/smart_index.py`

```python
def main():
    # ... existing argument parsing ...
    
    # Add background mode support
    parser.add_argument('--background', action='store_true',
        help='Run in background mode (suppress stdout, use logging)')
    
    args, unknown_args = parser.parse_known_args()
    
    # Configure output mode
    if args.background:
        # Suppress print statements, use logging only
        setup_background_logging()
    else:
        # Normal interactive mode
        setup_interactive_logging()
    
    # ... rest of existing logic ...

def setup_background_logging():
    """Configure logging for background mode"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('/tmp/ragex_background.log'),
            logging.StreamHandler()  # Still log to daemon logs
        ]
    )
    
    # Override print function to use logging
    import builtins
    def log_print(*args, **kwargs):
        message = ' '.join(str(arg) for arg in args)
        logging.info(message)
    builtins.print = log_print

def setup_interactive_logging():
    """Configure logging for interactive mode (current behavior)"""
    # Same as current setup
    pass
```

### Phase 3: Status and Progress Tracking

#### Enhanced Status Command
```python
def cmd_status(self, args: argparse.Namespace) -> int:
    """Enhanced status command"""
    if not self.is_daemon_running():
        print(f"❌ No daemon running for {self.project_name}")
        return 1
    
    # Get daemon status
    result = self.exec_via_daemon('status', [], use_tty=False)
    
    # Also check for background tasks
    bg_result = self.exec_via_daemon('init_status', [], use_tty=False)
    
    return result
```

#### Log Integration
- Background indexing progress goes to daemon logs
- Users can follow with `ragex log -f`
- Background completion/failure logged with clear markers

## Migration and Compatibility

### Backward Compatibility
- **`ragex start`** and **`ragex index`** remain unchanged (sync behavior)
- **`ragex init --sync`** provides identical behavior to current commands
- **No breaking changes** to existing workflows

### Migration Path
1. **Phase 1:** Add `ragex init` command with both modes
2. **Phase 2:** Update documentation to recommend `ragex init` for new users
3. **Phase 3:** Consider deprecating `ragex start` in favor of `ragex init --sync`

### User Education
```bash
# Current users (no change needed)
ragex start                          # Still works exactly the same

# New recommended approach
ragex init                           # Quick async initialization
ragex init --sync                    # If you need blocking behavior

# Status and management
ragex init --status                  # Check if background indexing running
ragex log -f                        # Follow background progress
ragex init --cancel                  # Cancel if needed
```

## Benefits of This Approach

### User Experience Improvements
1. **Faster CLI responses:** Users don't wait for long indexing operations
2. **Non-blocking workflow:** Can continue working while indexing happens
3. **Better project setup:** Quick initialization, indexing happens in background
4. **Flexible control:** Choose sync vs async based on needs

### Development Benefits
1. **Cleaner separation:** Init vs ongoing operations
2. **Better resource management:** Background tasks properly managed
3. **Improved testing:** Can test async vs sync behaviors separately
4. **Enhanced monitoring:** Better visibility into background operations

### Operational Benefits
1. **Reduced CLI timeouts:** No more long-running CLI commands
2. **Better daemon utilization:** Daemon handles background work efficiently
3. **Improved error recovery:** Background failures don't block CLI
4. **Enhanced logging:** Clear background operation audit trail

## Implementation Phases

### Phase 1: Basic Implementation (Week 1)
- [ ] Add `ragex init` command to CLI with `--sync` support
- [ ] Implement sync mode (identical to current behavior)
- [ ] Add basic async mode (daemon starts, returns immediately)
- [ ] Basic testing and documentation

### Phase 2: Background Processing (Week 2)
- [ ] Implement daemon background task management
- [ ] Add `init_async`, `init_status`, `init_cancel` daemon handlers
- [ ] Update `smart_index.py` for background mode
- [ ] Comprehensive testing of async workflows

### Phase 3: Enhanced Status and Logging (Week 3)
- [ ] Enhanced status reporting with background task info
- [ ] Improved logging and progress tracking for background mode
- [ ] Better error handling and recovery for background tasks
- [ ] User documentation and migration guides

### Phase 4: Polish and Optimization (Week 4)
- [ ] Performance optimizations for background tasks
- [ ] Advanced features (progress callbacks, notifications)
- [ ] Comprehensive test suite covering all scenarios
- [ ] Production readiness assessment

## Success Criteria

### Functional Requirements
- ✅ `ragex init` provides fast, async project initialization
- ✅ `ragex init --sync` maintains current blocking behavior
- ✅ Background indexing works reliably without user intervention
- ✅ Status commands provide clear visibility into background operations
- ✅ Error handling robust for both sync and async modes

### Performance Requirements
- ✅ `ragex init` returns in < 5 seconds (daemon startup + task trigger)
- ✅ Background indexing performance matches current sync performance
- ✅ Daemon resource usage remains reasonable with background tasks
- ✅ CLI responsiveness maintained during background operations

### User Experience Requirements
- ✅ Intuitive command interface (`--sync` for blocking, default for async)
- ✅ Clear status feedback for background operations
- ✅ Simple cancellation mechanism for background tasks
- ✅ Smooth migration path from current workflows

This implementation plan provides a comprehensive approach to adding async initialization while maintaining full compatibility with existing workflows and improving the overall user experience.