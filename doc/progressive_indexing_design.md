# Progressive Indexing Design

## Overview
Allow the MCP server to start immediately and be useful while building the index in the background. Users can query with partial results that improve over time.

## Process Pool Explanation

The process pool solves the Python GIL (Global Interpreter Lock) problem:

```python
# Without process pool - blocks other async tasks during CPU work
async def index_file(file_path):
    symbols = await extract_symbols(file_path)  # CPU intensive - blocks!
    embeddings = create_embeddings(symbols)     # CPU intensive - blocks!
    
# With process pool - CPU work happens in separate process
async def index_file(file_path):
    loop = asyncio.get_event_loop()
    # This returns immediately, work happens in another process
    result = await loop.run_in_executor(
        process_pool,
        cpu_intensive_work,
        file_path
    )
```

## Progressive Indexing Architecture

### 1. Server Startup Flow

```python
class ProgressiveIndexer:
    def __init__(self):
        self.index_state = IndexState.INITIALIZING
        self.files_total = 0
        self.files_indexed = 0
        self.partial_results_warning = True
        
    async def initialize(self):
        """Initialize on server startup"""
        # Check if index exists
        if self.has_existing_index():
            self.index_state = IndexState.READY
            self.partial_results_warning = False
            logger.info("Found existing index")
            
            # Start incremental watcher
            await self.start_incremental_watcher()
        else:
            # Start progressive indexing
            self.index_state = IndexState.BUILDING
            logger.info("No index found - starting progressive build")
            await self.start_progressive_build()
    
    async def start_progressive_build(self):
        """Build index progressively while serving requests"""
        # Count files first (fast)
        self.files_total = await self.count_files()
        
        # Start background indexing with process pool
        self.index_task = asyncio.create_task(
            self._progressive_index_worker()
        )
```

### 2. Intelligent Query Handling

```python
@app.tool()
async def search_code(query: str, mode: str = "auto") -> Dict:
    """Search code - works immediately with partial results"""
    
    # Add index state to response
    index_status = indexer.get_status()
    
    if index_status.state == IndexState.BUILDING:
        # Include warning about partial results
        response = {
            "warning": f"Index building: {index_status.progress}% complete. Results may be incomplete.",
            "index_state": "building",
            "coverage": index_status.coverage
        }
    
    # Perform search on whatever is indexed so far
    results = await execute_search(query, mode)
    
    # For semantic search during indexing
    if mode == "semantic" and index_status.state == IndexState.BUILDING:
        # Fallback to enhanced regex search
        if len(results) == 0:
            response["fallback_used"] = True
            results = await execute_regex_search(query)
            response["fallback_reason"] = "Semantic index still building"
    
    response["results"] = results
    return response
```

### 3. Process Pool Configuration

```python
class IndexProcessPool:
    def __init__(self, max_workers: int = None):
        # Auto-detect optimal workers
        if max_workers is None:
            cpu_count = os.cpu_count() or 2
            # Use half CPUs for indexing, leave half for MCP
            max_workers = max(1, cpu_count // 2)
        
        self.executor = ProcessPoolExecutor(
            max_workers=max_workers,
            initializer=self._worker_init
        )
        
    def _worker_init(self):
        """Initialize each worker process"""
        # Load Tree-sitter languages once per worker
        initialize_parsers()
        # Set lower priority
        os.nice(10)  # Lower priority on Unix-like systems
```

### 4. Progressive Indexing Strategy

```python
class ProgressiveIndexer:
    async def _progressive_index_worker(self):
        """Index files progressively with smart prioritization"""
        
        # Phase 1: Index high-value files first
        priority_patterns = [
            "**/index.*",      # Entry points
            "**/main.*",       # Main files  
            "**/server.*",     # Servers
            "**/api/*",        # API definitions
            "**/core/*",       # Core logic
        ]
        
        # Phase 2: Regular source files
        # Phase 3: Test files
        # Phase 4: Config/docs
        
        files_by_priority = self.prioritize_files(all_files)
        
        for priority_group in files_by_priority:
            for batch in chunks(priority_group, batch_size=10):
                # Process batch in process pool
                await self.index_batch_async(batch)
                
                # Update progress
                self.files_indexed += len(batch)
                self.update_progress()
                
                # Yield to MCP requests
                await asyncio.sleep(0)
```

### 5. Smart Batching

```python
async def index_batch_async(self, files: List[Path]):
    """Index a batch of files without blocking MCP"""
    
    # Separate CPU-intensive work
    loop = asyncio.get_event_loop()
    
    # Step 1: Parse files in process pool (CPU intensive)
    parse_futures = []
    for file in files:
        future = loop.run_in_executor(
            self.process_pool,
            parse_file_sync,  # Runs in separate process
            file
        )
        parse_futures.append(future)
    
    # Wait for parsing to complete
    parsed_results = await asyncio.gather(*parse_futures)
    
    # Step 2: Create embeddings (can batch for efficiency)
    embeddings = await self.create_embeddings_batch(parsed_results)
    
    # Step 3: Update vector store (I/O bound, OK in main process)
    await self.vector_store.add_batch(parsed_results, embeddings)
```

## Configuration Options

```python
# Environment variables
RAGEX_PROGRESSIVE_INDEX=true       # Enable progressive indexing
RAGEX_INDEX_WORKERS=2              # Number of worker processes
RAGEX_INDEX_PRIORITY=low           # Process priority
RAGEX_INITIAL_BATCH_SIZE=50        # Files per batch during initial index
RAGEX_INDEX_HIGH_WATER_MARK=1000   # Pause indexing if queue > this
```

## User Experience

### 1. First Run (No Index)
```
$ ./run_server.sh
🚀 CodeRAG MCP Server starting...
📊 No index found - starting progressive indexing
📁 Found 1,847 files to index
🏗️ Building index in background (10% complete)
✅ Server ready - search available (partial results)
```

### 2. Searching During Index Build
```
User: search_code("handle authentication")

Response:
{
  "warning": "Index 45% complete. Results may be incomplete.",
  "coverage": {
    "files_indexed": 831,
    "files_total": 1847,
    "percent": 45
  },
  "results": [...],  // Whatever is indexed so far
  "suggestions": [
    "Try regex search for more complete results",
    "Full semantic search available in ~2 minutes"
  ]
}
```

### 3. Index Completion
```
🎉 Index complete! 1,847 files indexed in 3m 12s
✨ Full semantic search now available
💾 Index saved to ./chroma_db
```

## Advantages

1. **Immediate Availability** - Server usable right away
2. **Progressive Enhancement** - Results improve over time  
3. **Non-Blocking** - MCP remains responsive during indexing
4. **Smart Prioritization** - Important files indexed first
5. **Graceful Degradation** - Falls back to regex when needed
6. **Resource Friendly** - Configurable CPU usage
7. **Transparent** - Users know index state

## State Machine

```
INITIALIZING -> READY (if index exists)
            \-> BUILDING -> READY (after completion)
                        \-> ERROR (on failure)

During BUILDING:
- Semantic search works with partial data
- Warns users about incomplete coverage  
- Shows progress percentage
- Falls back to regex if needed
```

## Integration with Incremental Updates

Once initial index is built:
1. State transitions to READY
2. Incremental file watcher starts
3. Progressive indexer task terminates
4. System switches to incremental update mode

This provides seamless experience from first run through ongoing usage!