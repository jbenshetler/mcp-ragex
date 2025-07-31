# Search Unification Analysis

## Current Architecture

Both bash `ragex` and Python `ragex.py` follow the EXACT SAME execution path:

```
User → ragex/ragex.py → docker exec → socket_client → daemon → SearchHandler → SearchClient
```

## Execution Flow Trace

### 1. Command Entry
- **Bash**: `exec_via_daemon "search" "$@"`
- **Python**: `exec_via_daemon('search', cmd_args)`

### 2. Docker Execution
Both run: `docker exec -i[t] {container} python -m src.socket_client search [args]`

### 3. Socket Communication
`src/socket_client.py` sends JSON to daemon:
```json
{
  "command": "search",
  "args": ["query", "--limit", "50", ...]
}
```

### 4. Daemon Routing
`src/socket_daemon.py`:
- Checks if ChromaDB exists at `{project_data_dir}/chroma_db`
- Routes to `SearchHandler.handle(args)`

### 5. Search Handler
`src/daemon/handlers/search.py`:
```python
# Determines project directory
project_data_dir = os.environ.get('RAGEX_PROJECT_DATA_DIR')
if not project_data_dir:
    project_name = os.environ.get('PROJECT_NAME', 'admin')
    project_data_dir = f'/data/projects/{project_name}'

# Creates SearchClient (CACHED!)
if not self.search_client or self._project_changed(project_data_dir):
    self.search_client = SearchClient(index_dir=project_data_dir)
```

### 6. Search Client
`src/cli/search.py`:
```python
# Looks for ChromaDB
index_path = Path(index_dir) / "chroma_db"
if index_path.exists():
    # Initialize semantic search
else:
    # No semantic search
```

## Root Cause Analysis

### The Problem: SearchClient Caching

The SearchHandler caches the SearchClient instance. If the client was created when:
1. ChromaDB didn't exist yet
2. Or with wrong project directory
3. Or before semantic dependencies were available

Then semantic search will remain disabled until:
- The daemon is restarted
- The project directory changes

### Why Bash Works but Python Doesn't

Possible scenarios:
1. **Daemon timing**: Python ragex.py might have started daemon before index was built
2. **Cached state**: SearchClient was created without semantic search and cached
3. **Environment differences**: Different PROJECT_NAME when daemon started

## Code Sharing Analysis

### What IS Shared
- ✅ Socket communication protocol
- ✅ Daemon command routing
- ✅ SearchHandler logic
- ✅ SearchClient implementation
- ✅ Argument parsing (via CLI module)
- ✅ Search execution

### What CANNOT Be Shared
1. **Initial argument parsing**: 
   - Bash uses positional args
   - Python uses argparse
   - **Justification**: Different UI paradigms

2. **Docker container management**:
   - Bash uses shell commands
   - Python uses subprocess
   - **Justification**: Language constraints

3. **Result display**:
   - Bash pipes directly
   - Python might need JSON mode
   - **Justification**: Different output requirements

## Unification Plan

### 1. Fix SearchClient Caching Issue

**Option A: Force Refresh**
```python
# In SearchHandler.handle()
if args and '--force-refresh' in args:
    self.search_client = None
```

**Option B: Check ChromaDB Status**
```python
# In SearchHandler.handle()
if self.search_client and not self.search_client.semantic_searcher:
    # Check if ChromaDB now exists
    chroma_path = Path(project_data_dir) / "chroma_db"
    if chroma_path.exists():
        # Recreate client
        self.search_client = SearchClient(index_dir=project_data_dir)
```

**Option C: No Caching (Recommended)**
```python
# Always create fresh SearchClient
# Performance impact is minimal since embedding model is cached globally
```

### 2. Improve Debugging

Add debug logs to show:
- When SearchClient is created vs reused
- ChromaDB path being checked
- Semantic search initialization status

### 3. Environment Consistency

Ensure both bash and Python:
- Pass same PROJECT_NAME to daemon
- Use same project ID generation
- Handle WORKSPACE_PATH identically

## Recommended Changes

### 1. Remove SearchClient Caching
```python
# src/daemon/handlers/search.py
async def handle(self, args: list) -> Dict[str, Any]:
    # Always create fresh client to pick up index changes
    project_data_dir = self._get_project_dir()
    self.search_client = SearchClient(index_dir=project_data_dir)
```

### 2. Add Semantic Search Status
```python
# src/cli/search.py
def get_status(self) -> Dict[str, Any]:
    return {
        'semantic_available': self.semantic_searcher is not None,
        'index_path': self.index_path if hasattr(self, 'index_path') else None,
        'symbol_count': self.get_symbol_count() if self.semantic_searcher else 0
    }
```

### 3. Improve Error Reporting
Instead of silently returning empty results, report why semantic search isn't available.

## Conclusion

The code IS maximally shared - both bash and Python use identical execution paths. The issue is a caching bug in the shared SearchHandler that affects both implementations differently based on daemon lifecycle.

The fix is simple: remove or improve the SearchClient caching logic.