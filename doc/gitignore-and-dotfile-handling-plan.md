# Plan: Gitignore and Dotfile Handling for Semantic Search

## Overview

To achieve parity with ripgrep's file handling behavior, we need to implement support for:
1. Default exclusion patterns (always active)
2. `.gitignore` files at every directory level
3. `.rgignore` files at every directory level (already renamed from `.mcpignore`)
4. Automatic exclusion of dotfiles and dot directories
5. Hot reloading when ignore files change
6. Database cleanup when files become ignored

## Current State

- We currently support `.rgignore` (formerly `.mcpignore`) files through our custom IgnoreManager
- Ripgrep natively handles `.gitignore` and `.rgignore` for regex/symbol search
- Semantic search uses our custom pattern matcher which doesn't handle `.gitignore`
- No automatic dotfile exclusion in semantic indexing
- No database cleanup when ignore patterns change

## Pattern Precedence

The precedence order (later overrides earlier):
1. **Default patterns** (built-in exclusions like `__pycache__`, `node_modules`)
2. **`.gitignore`** files (at each directory level)
3. **`.rgignore`** files (at each directory level, highest precedence)

This means:
- Default patterns are ALWAYS active unless explicitly overridden
- `.gitignore` can override default patterns
- `.rgignore` can override both defaults and `.gitignore`

## Implementation Plan

### Phase 1: Add Gitignore Support to IgnoreManager

1. **Update IgnoreFileLoader** (`src/ragex_core/ignore/file_loader.py`)
   - Add support for loading `.gitignore` files in addition to `.rgignore`
   - Handle gitignore-specific syntax differences (if any)

2. **Update IgnoreManager** (`src/ragex_core/ignore/manager.py`)
   - Scan for both `.gitignore` and `.rgignore` files at each directory level
   - Apply precedence rules: default patterns < `.gitignore` < `.rgignore`
   - Ensure default patterns are ALWAYS included as the base layer
   - Cache both file types in the rule cache

3. **Update Constants** (`src/ragex_core/ignore/constants.py`)
   - Add `GITIGNORE_FILENAME = ".gitignore"`
   - Keep `DEFAULT_EXCLUSIONS` list for built-in patterns
   - Add configuration for supported ignore file types

### Phase 2: Implement Dotfile/Dotdir Exclusion

1. **Add Default Dotfile Rules to DEFAULT_EXCLUSIONS**
   - Add pattern `.*` to exclude all dotfiles
   - Add pattern `.*/**` to exclude everything inside dot directories
   - These are part of the default patterns (lowest precedence)

2. **Update IgnoreRuleEngine** (`src/ragex_core/ignore/rule_engine.py`)
   - Ensure default patterns are compiled first
   - Allow override via explicit inclusion patterns (e.g., `!.env.example` in `.gitignore` or `.rgignore`)

### Phase 3: Hot Reload Support for All Ignore Files

1. **Update WatchdogMonitor** (`src/watchdog_monitor.py`)
   - Watch for changes to both `.gitignore` and `.rgignore` files
   - Trigger cleanup and reindexing when either type changes

2. **Update IndexingFileHandler** (`src/ragex_core/indexing_file_handler.py`)
   - Handle both ignore file types in change detection
   - Properly debounce changes to avoid excessive reindexing

### Phase 4: Database Cleanup on Ignore Changes

1. **Create Cleanup Handler** (`src/ragex_core/ignore_cleanup_handler.py`)
   ```python
   class IgnoreCleanupHandler:
       def __init__(self, vector_store: CodeVectorStore, ignore_manager: IgnoreManager):
           self.vector_store = vector_store
           self.ignore_manager = ignore_manager
           self.last_patterns_snapshot = self._get_current_patterns()
       
       async def cleanup_on_pattern_change(self):
           """Called when ignore files change"""
           new_patterns = self._get_current_patterns()
           if new_patterns != self.last_patterns_snapshot:
               await self._cleanup_newly_ignored_files()
               self.last_patterns_snapshot = new_patterns
       
       async def periodic_cleanup(self):
           """Called during continuous indexing cycles"""
           # Get all files in vector store
           indexed_files = await self.vector_store.list_all_files()
           
           # Check each against current patterns
           files_to_remove = []
           for file_path in indexed_files:
               if self.ignore_manager.should_ignore(file_path):
                   files_to_remove.append(file_path)
           
           # Batch remove from vector store
           if files_to_remove:
               await self.vector_store.delete_files(files_to_remove)
               logger.info(f"Cleaned up {len(files_to_remove)} ignored files")
   ```

2. **Integration Points**
   - **On Change Detection**: When watchdog detects `.gitignore`/`.rgignore` changes
     - Immediately run `cleanup_on_pattern_change()`
     - Then trigger reindexing of affected directories
   
   - **During Continuous Indexing**: Every 5-minute cycle
     - Run `periodic_cleanup()` to catch any drift
     - Ensures database stays consistent even if change detection missed something
   
   - **On Manual Index Command**: When user runs `ragex index`
     - Run cleanup before indexing to start fresh

3. **Cleanup Timing Details**
   - **Immediate cleanup** on ignore file changes (< 1 second)
   - **Periodic cleanup** every 5 minutes with continuous indexing
   - **Pre-index cleanup** before any indexing operation
   - All cleanup operations are logged for transparency

### Phase 5: Replace `init` Command with `exclusions` Command

1. **Remove `init` Command**
   - Remove from entrypoint.sh
   - Remove from command parsers
   - Remove init handler

2. **Add `exclusions` Command**
   - Purpose: Show default exclusion patterns in `.rgignore` compatible format
   - Output includes:
     - Header explaining these are default patterns
     - All patterns from `DEFAULT_EXCLUSIONS`
     - Comments explaining how to override (use `!pattern`)
   
   Example output:
   ```
   # Default exclusion patterns used by ragex
   # These are always active unless overridden in .gitignore or .rgignore
   # To include an excluded pattern, use !pattern (e.g., !.env.example)
   
   # Python
   __pycache__/**
   *.pyc
   .venv/**
   
   # Node.js
   node_modules/**
   
   # Dotfiles and directories
   .*
   .*/**
   
   # ... rest of default patterns
   ```

### Phase 6: Update Documentation

1. **Update README.md**
   - Add comprehensive section on exclusion logic
   - Include examples of pattern precedence
   - Show how to override default exclusions
   
   Example section for README:
   ```markdown
   ## File Exclusion and Ignore Patterns
   
   Ragex uses a three-layer exclusion system that matches ripgrep's behavior:
   
   ### Pattern Precedence (highest to lowest)
   1. `.rgignore` - Ragex-specific ignore patterns (highest priority)
   2. `.gitignore` - Git ignore patterns
   3. Default exclusions - Built-in patterns (lowest priority)
   
   ### Default Exclusions
   By default, ragex excludes common build artifacts and dependencies:
   - Python: `__pycache__/`, `*.pyc`, `.venv/`, etc.
   - Node.js: `node_modules/`
   - Dotfiles: `.*` and everything in dot directories `.*/**`
   - And many more...
   
   Run `ragex exclusions` to see the full list.
   
   ### Overriding Default Exclusions
   You can include files that are excluded by default using the `!` prefix:
   
   **Example 1**: Include `.env.example` (excluded by default as a dotfile)
   ```
   # In .gitignore or .rgignore
   !.env.example
   ```
   
   **Example 2**: Include specific files in `node_modules`
   ```
   # In .rgignore (highest priority)
   !node_modules/my-local-package/**
   ```
   
   **Example 3**: Override in different layers
   ```
   # Default excludes all .pyc files
   # In .gitignore: still excluded
   # In .rgignore: include test.pyc
   !test.pyc
   ```
   
   ### Ignore File Locations
   Both `.gitignore` and `.rgignore` files are processed at every directory level,
   with patterns applying to that directory and its subdirectories.
   ```

### Phase 7: Testing and Validation

1. **Test Cases**
   - Verify default patterns are always active
   - Test precedence: defaults < .gitignore < .rgignore
   - Nested `.gitignore` and `.rgignore` files
   - Dotfile and dot directory exclusion
   - Override patterns (e.g., `!.env.example`)
   - Hot reload triggering cleanup
   - Periodic cleanup during continuous indexing
   - Database consistency after cleanup

2. **Performance Testing**
   - Large repositories with many ignore files
   - Deep directory structures
   - Frequent ignore file changes
   - Cleanup performance with large vector stores

## Implementation Order

1. Add gitignore support to IgnoreManager (Phase 1)
2. Implement dotfile exclusion in defaults (Phase 2)
3. Update hot reload for all ignore types (Phase 3)
4. Implement database cleanup with dual triggers (Phase 4)
5. Replace init with exclusions command (Phase 5)
6. Update documentation with examples (Phase 6)
7. Comprehensive testing (Phase 7)

## Risk Mitigation

1. **Performance Impact**
   - Multiple ignore files could slow down indexing
   - Mitigation: Efficient caching and rule compilation

2. **Data Loss**
   - Database cleanup could remove files unintentionally
   - Mitigation: Detailed logging, test thoroughly

3. **Pattern Conflicts**
   - Complex interaction between three layers of patterns
   - Mitigation: Clear precedence rules, comprehensive testing

## Success Criteria

- Semantic search excludes the same files as ripgrep
- Default patterns remain active regardless of ignore files
- Changes to `.gitignore` or `.rgignore` trigger immediate cleanup
- Periodic cleanup maintains database consistency
- Dotfiles and dot directories are excluded by default
- `exclusions` command helps users understand what's excluded
- README clearly explains exclusion logic with practical examples
- Performance remains acceptable for large repositories