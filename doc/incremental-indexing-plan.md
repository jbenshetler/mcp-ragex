# Incremental Indexing Implementation Plan

## Overview

This document outlines the implementation plan for efficient incremental indexing in RAGex. The goal is to minimize I/O and processing by tracking individual file checksums and only re-indexing files that have actually changed.

## Current Issues

1. **Workspace checksum is wasteful** - Requires reading all files twice
2. **No file-level tracking** - Can't identify which specific files changed
3. **Prompting in non-interactive mode** - `build_semantic_index.py` prompts when index exists
4. **Incomplete startup reconciliation** - Changes during daemon downtime aren't detected efficiently

## Design Principles

1. **Single file read** - Each file should be read only once per indexing operation
2. **Content-based** - Use SHA256 of file contents, not timestamps (git-friendly)
3. **Incremental updates** - Only process files that actually changed
4. **No prompts** - Fully automated operation in daemon mode

## Implementation Plan

### Phase 1: File Checksum Storage

#### 1.1 Extend Vector Store Metadata

```python
# In CodeVectorStore.add_symbols()
metadata = {
    "symbol_name": symbol['name'],
    "symbol_type": symbol['type'], 
    "file_path": symbol['file'],
    "file_checksum": symbol.get('file_checksum'),  # NEW
    "line_start": symbol['line'],
    # ... other fields
}
```

#### 1.2 Add Checksum Retrieval Methods

```python
class CodeVectorStore:
    def get_file_checksums(self) -> Dict[str, str]:
        """
        Retrieve all stored file checksums.
        Returns: {file_path: checksum}
        """
        
    def get_files_by_checksum(self, checksum: str) -> List[str]:
        """
        Get all files with a specific checksum (useful for detecting moves).
        """
```

### Phase 2: File Scanning and Comparison

#### 2.1 Create File Checksum Module

```python
# src/lib/file_checksum.py

def calculate_file_checksum(file_path: Path) -> str:
    """Calculate SHA256 checksum of a single file."""
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()

def scan_workspace_files(workspace_path: Path, ignore_manager) -> Dict[str, str]:
    """
    Scan workspace and calculate checksums for all non-ignored files.
    Returns: {relative_file_path: checksum}
    """
    results = {}
    for file_path in workspace_path.rglob('*'):
        if file_path.is_file() and not ignore_manager.should_ignore(str(file_path)):
            rel_path = str(file_path.relative_to(workspace_path))
            results[rel_path] = calculate_file_checksum(file_path)
    return results

def compare_checksums(current: Dict[str, str], stored: Dict[str, str]) -> Tuple[List[str], List[str], List[str]]:
    """
    Compare current vs stored checksums.
    Returns: (added_files, removed_files, modified_files)
    """
    current_files = set(current.keys())
    stored_files = set(stored.keys())
    
    added = list(current_files - stored_files)
    removed = list(stored_files - current_files)
    
    modified = []
    for file in current_files & stored_files:
        if current[file] != stored[file]:
            modified.append(file)
    
    return added, removed, modified
```

### Phase 3: Rewrite smart_index.py

```python
def main():
    # ... initialization ...
    
    # Check if index exists
    index_exists = (Path(project_data_dir) / 'chroma_db').exists()
    
    if not index_exists:
        # First time - full index
        print("📊 Creating initial index...")
        run_full_index()  # Call build_semantic_index.py
    else:
        # Incremental update
        print("🔍 Checking for file changes...")
        
        # Get stored checksums from vector store
        vector_store = CodeVectorStore(persist_directory=...)
        stored_checksums = vector_store.get_file_checksums()
        
        # Scan current files
        current_checksums = scan_workspace_files(workspace_path, ignore_manager)
        
        # Compare
        added, removed, modified = compare_checksums(current_checksums, stored_checksums)
        
        if not (added or removed or modified):
            print("✅ Index is up-to-date")
            return
        
        # Perform incremental update
        print(f"📝 Updating index: +{len(added)} ~{len(modified)} -{len(removed)} files")
        
        indexer = CodeIndexer(persist_directory=...)
        
        # Remove deleted files
        for file_path in removed:
            vector_store.delete_by_file(file_path)
        
        # Update modified and new files
        for file_path in added + modified:
            # Calculate checksum once and pass it through
            checksum = current_checksums[file_path]
            await indexer.update_file(file_path, file_checksum=checksum)
        
        print("✅ Index updated")
```

### Phase 4: Integrate with Watchdog

#### 4.1 Update IndexingFileHandler

```python
def on_modified(self, event):
    if not event.is_directory:
        # Calculate checksum for the modified file
        checksum = calculate_file_checksum(event.src_path)
        # Pass checksum through the queue
        self.queue.add_file(event.src_path, checksum)
```

#### 4.2 Update _handle_incremental_index

```python
async def _handle_incremental_index(self, file_changes: List[Tuple[Path, str]]):
    """
    Handle incremental indexing with checksums.
    file_changes: List of (file_path, checksum) tuples
    """
    for file_path, checksum in file_changes:
        await indexer.update_file(file_path, file_checksum=checksum)
```

### Phase 5: Optimization

#### 5.1 Checksum Caching

For large files, we can optimize by checking size+mtime before computing checksum:

```python
FileInfo = namedtuple('FileInfo', ['size', 'mtime', 'checksum'])

def should_recompute_checksum(file_path: Path, cached_info: FileInfo) -> bool:
    """Check if file stats changed before expensive checksum calculation."""
    stat = file_path.stat()
    return (stat.st_size != cached_info.size or 
            stat.st_mtime != cached_info.mtime)
```

#### 5.2 Parallel Processing

For initial indexing of large codebases:

```python
async def scan_workspace_files_parallel(workspace_path: Path, ignore_manager):
    """Scan files in parallel using asyncio."""
    files = [f for f in workspace_path.rglob('*') 
             if f.is_file() and not ignore_manager.should_ignore(str(f))]
    
    # Process in batches to avoid too many open files
    batch_size = 100
    results = {}
    
    for i in range(0, len(files), batch_size):
        batch = files[i:i + batch_size]
        tasks = [calculate_file_checksum_async(f) for f in batch]
        checksums = await asyncio.gather(*tasks)
        
        for file, checksum in zip(batch, checksums):
            rel_path = str(file.relative_to(workspace_path))
            results[rel_path] = checksum
    
    return results
```

## Benefits

1. **Efficient** - Each file read only once
2. **Accurate** - Exact detection of changed files
3. **Git-friendly** - Content-based, not timestamp-based
4. **Scalable** - Only processes what changed
5. **No prompts** - Fully automated

## Testing Strategy

1. **Unit tests** for checksum calculation and comparison
2. **Integration tests** for incremental indexing
3. **Performance tests** comparing full vs incremental indexing
4. **Edge cases**: moved files, renamed files, permission changes

## Phase 6: Periodic Rescan Safety Net

To handle edge cases where watchdog might miss files, implement a periodic rescan:

```python
class PeriodicRescanThread:
    """
    Background thread that periodically scans for missing files.
    Runs every 15 minutes after the last scan completes.
    """
    
    async def rescan_loop(self):
        while self.running:
            # Wait 15 minutes
            await asyncio.sleep(900)
            
            # Get all files in workspace
            current_files = scan_workspace_files(workspace_path, ignore_manager)
            
            # Get all files in index
            indexed_files = vector_store.get_file_checksums()
            
            # Find discrepancies
            missing_files = set(current_files.keys()) - set(indexed_files.keys())
            
            if missing_files:
                logger.info(f"Periodic rescan found {len(missing_files)} missing files")
                # Queue them through normal indexing path
                for file_path in missing_files:
                    checksum = current_files[file_path]
                    await indexing_queue.add_file(file_path, checksum)
```

## Success Metrics

- Initial index: Same speed as current implementation
- No changes: < 1 second to verify (just stat files)
- Small changes (1-10 files): < 5 seconds to update
- Large changes (100+ files): Proportional to changed files, not total files
- Periodic rescan: Catches 100% of missed files within 15 minutes