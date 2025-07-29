# Socket Daemon Architecture Fix Plan

## Current State Analysis

### What's Broken
1. **Search is completely non-functional** - Socket daemon crashes after module loading
2. **`ragex init` is broken** - init command handler has issues  
3. **Performance is terrible** - Each command takes 14-24+ seconds due to restarts
4. **Module initialization conflicts** - Importing from src.server runs module-level code
5. **Architecture is fragile** - Multiple layers of hacks and workarounds

### Root Causes
1. **Circular dependencies** - Socket daemon imports from server.py which has module-level initialization
2. **Poor module structure** - No separation between library code and executable code
3. **Improper state management** - Daemon tries to pre-load modules but crashes on usage
4. **Mixed responsibilities** - Socket daemon handles too many different command types
5. **No proper error handling** - Failures cascade without recovery

## Proposed Solution Architecture

### 1. Module Restructuring (Priority: Critical)

**Goal**: Separate library code from executable code to prevent initialization issues

```
src/
├── lib/                      # Pure library code (no side effects)
│   ├── __init__.py
│   ├── searcher.py          # RipgrepSearcher class only
│   ├── pattern_matcher.py   # PatternMatcher class only
│   ├── vector_store.py      # VectorStore class only
│   ├── embedding_manager.py # EmbeddingManager class only
│   └── ignore_manager.py    # Ignore file handling
├── cli/                     # CLI entry points
│   ├── __init__.py
│   ├── search.py           # Search command implementation
│   ├── index.py            # Index command implementation
│   ├── init.py             # Init command implementation
│   └── serve.py            # MCP server implementation
├── daemon/                  # Daemon-specific code
│   ├── __init__.py
│   ├── socket_daemon.py    # Socket daemon server
│   ├── socket_client.py    # Socket client
│   └── handlers/           # Command handlers
│       ├── __init__.py
│       ├── search.py       # Search handler
│       ├── index.py        # Index handler
│       └── init.py         # Init handler
└── server.py               # MCP server (imports from lib/)
```

### 2. Socket Daemon Rewrite (Priority: Critical)

**Goal**: Create a stable daemon that properly manages pre-loaded modules

Key changes:
- Remove all imports from src.server
- Create dedicated handler classes for each command
- Proper error isolation between handlers
- Lazy loading of heavy modules (torch, sentence_transformers)
- Health check endpoint for monitoring

```python
# src/daemon/socket_daemon.py
class RagexSocketDaemon:
    def __init__(self):
        self.handlers = {}
        self.modules = {}
        self._load_core_modules()  # Only lightweight modules
    
    def _load_core_modules(self):
        # Import only pure library modules
        from src.lib.pattern_matcher import PatternMatcher
        from src.lib.ignore_manager import IgnoreManager
        self.modules['pattern_matcher'] = PatternMatcher
        self.modules['ignore_manager'] = IgnoreManager
    
    async def get_handler(self, command: str):
        if command not in self.handlers:
            # Lazy load handlers
            if command == 'search':
                from src.daemon.handlers.search import SearchHandler
                self.handlers[command] = SearchHandler(self.modules)
            elif command == 'index':
                from src.daemon.handlers.index import IndexHandler
                self.handlers[command] = IndexHandler(self.modules)
            # etc...
        return self.handlers[command]
```

### 3. Command Handler Architecture (Priority: High)

**Goal**: Isolate command logic and enable proper module reuse

Example search handler:
```python
# src/daemon/handlers/search.py
class SearchHandler:
    def __init__(self, shared_modules):
        self.shared_modules = shared_modules
        self.search_client = None
    
    async def handle(self, args: list) -> dict:
        # Lazy initialize search client
        if not self.search_client:
            self._init_search_client()
        
        # Parse args and execute search
        # Return standardized response
```

### 4. Performance Optimization Strategy (Priority: High)

**Phase 1**: Get it working
- Fix module imports and circular dependencies
- Ensure daemon starts and stays running
- Basic command execution through socket

**Phase 2**: Optimize startup
- Pre-load lightweight modules only
- Lazy load heavy modules on first use
- Cache initialized objects between requests

**Phase 3**: Advanced optimization
- Connection pooling for ChromaDB
- Shared memory for embeddings
- Process pool for parallel operations

### 5. Testing Strategy (Priority: High)

Create automated tests for each component:
- Unit tests for lib modules
- Integration tests for handlers
- End-to-end tests for full flow
- Performance benchmarks

Test script example:
```bash
#!/bin/bash
# tests/test_daemon_performance.sh

# Start daemon
ragex start

# Measure search performance
time ragex search "test query"
time ragex search "another query"  # Should be <1s

# Verify init works
ragex init

# Stop daemon
ragex stop
```

## Implementation Steps

### Phase 1: Emergency Fix (1-2 hours)
1. **Revert socket daemon to working state**
   - Remove all src.server imports
   - Disable module pre-loading
   - Use subprocess for all commands (like original)
   - Ensure daemon stays running

2. **Fix init command**
   - Create standalone init handler
   - Properly handle workspace paths
   - Test thoroughly

3. **Basic search functionality**
   - Subprocess-based search (slow but working)
   - Verify output format is correct
   - Ensure proper error handling

### Phase 2: Modularization (2-4 hours)
1. **Create lib/ directory structure**
   - Move pure classes to lib/
   - Remove all side effects from library code
   - Update imports throughout codebase

2. **Create CLI entry points**
   - Separate command implementations
   - Standardize argument parsing
   - Consistent output formatting

3. **Update daemon to use lib modules**
   - Import from lib/ instead of src/
   - Create proper handlers
   - Test each command type

### Phase 3: Performance Optimization (2-3 hours)
1. **Implement lazy loading**
   - Load modules on first use
   - Cache loaded modules
   - Monitor memory usage

2. **Optimize search path**
   - Pre-create search client
   - Reuse vector store connection
   - Minimize object creation

3. **Add monitoring**
   - Performance metrics
   - Health checks
   - Debug endpoints

### Phase 4: Testing & Documentation (1-2 hours)
1. **Create test suite**
   - Unit tests for components
   - Integration tests
   - Performance benchmarks

2. **Update documentation**
   - Architecture diagrams
   - Performance characteristics
   - Troubleshooting guide

## Success Metrics

1. **Functionality**
   - All commands work correctly
   - No crashes or hangs
   - Proper error messages

2. **Performance**
   - First search: <3 seconds (including daemon startup)
   - Subsequent searches: <1 second
   - Memory usage: <500MB

3. **Maintainability**
   - Clear module boundaries
   - No circular dependencies
   - Easy to debug and extend

## Risk Mitigation

1. **Rollback Plan**
   - Keep original code in git
   - Feature flag for daemon mode
   - Ability to disable and fall back to direct execution

2. **Gradual Migration**
   - Fix critical issues first
   - Modularize incrementally
   - Test at each step

3. **Monitoring**
   - Log all daemon operations
   - Track performance metrics
   - Alert on failures

## Conclusion

The current socket daemon implementation is fundamentally broken due to:
1. Circular dependencies with src.server
2. Poor module structure
3. Attempting to do too much at once

The fix requires:
1. Immediate reversion to a working state
2. Proper modularization of the codebase
3. Careful performance optimization
4. Comprehensive testing

This plan provides a clear path from the current broken state to a robust, performant solution that achieves sub-second search performance while maintaining code quality and reliability.