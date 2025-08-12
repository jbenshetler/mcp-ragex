# Enhanced Ignore File Processing Plan for Watchdog Integration

## Overview

This document outlines the plan to enhance the current `.rgignore` processing to support multi-level ignore files and prepare for integration with Python's `watchdog` library. The system will support hot reloading through external notification, with the filename centrally defined for easy future migration to `.ragexignore`.

## Current State Analysis

### Existing Implementation
- **Location**: `src/pattern_matcher.py`
- **Class**: `PatternMatcher`
- **Features**:
  - Reads single `.rgignore` file from working directory
  - Uses `pathspec` library for rgignore-style pattern matching
  - Provides validation and error reporting
  - Integrates with ripgrep for search exclusions
  - Has default exclusions (`.venv`, `__pycache__`, etc.)

### Limitations
1. Only reads from single `.rgignore` file in working directory
2. No support for nested `.rgignore` files in subdirectories
3. No hot reloading when `.rgignore` files change
4. Not designed for integration with file watchers
5. No caching of compiled patterns for performance

## Design Principles

1. **Central Filename Definition**: The ignore filename is defined in exactly one place
2. **External Change Notification**: System accepts notifications when ignore files change (no built-in watching)
3. **Multi-Level Support**: Handle ignore files at multiple directory levels
4. **Performance**: Efficient caching and incremental updates
5. **Future-Proof**: Easy migration path to `.ragexignore`

## Proposed Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    IgnoreManager (Main API)                  │
├─────────────────────────────────────────────────────────────┤
│ - Multi-level ignore file support                           │
│ - Reload on external notification                           │
│ - Central filename configuration                            │
│ - Caching and performance optimization                      │
└─────────────────────────────────────────────────────────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
    ┌───────────▼────────────┐   ┌───────────▼────────────┐
    │   IgnoreFileLoader     │   │   IgnoreRuleEngine    │
    ├────────────────────────┤   ├───────────────────────┤
    │ - Ignore file parsing  │   │ - Pattern compilation │
    │ - Validation           │   │ - Rule precedence     │
    │ - Error handling       │   │ - Path matching       │
    └────────────────────────┘   └───────────────────────┘
                               │
                ┌──────────────┴─────────────┐
                │                            │
    ┌───────────▼────────────┐   ┌───────────▼───────────┐
    │   IgnoreFileRegistry   │   │   IgnoreCache         │
    ├────────────────────────┤   ├───────────────────────┤
    │ - Track loaded files   │   │ - Compiled patterns   │
    │ - Hierarchy mapping    │   │ - Path decisions      │
    │ - Change detection     │   │ - LRU eviction        │
    └────────────────────────┘   └───────────────────────┘
```

### Key Features

#### 1. Multi-Level .rgignore Support

```python
# Example directory structure:
project/
├── .rgignore          # Root ignore file
├── src/
│   ├── .rgignore      # Overrides for src/
│   └── tests/
│       └── .rgignore  # Overrides for src/tests/
└── docs/
    └── .rgignore      # Overrides for docs/
```

**Rule Precedence**:
1. Most specific (deepest) `.rgignore` file takes precedence
2. Parent rules apply unless overridden by child
3. Negation patterns (`!pattern`) can re-include files
4. Global defaults apply to all levels

#### 2. Central Filename Configuration

```python
# In ignore/constants.py or similar
IGNORE_FILENAME = ".rgignore"  # Single source of truth

# Future migration is a one-line change:
# IGNORE_FILENAME = ".ragexignore"
```

#### 3. External Change Notification

```python
# External watchdog or monitoring system calls:
ignore_manager.notify_file_changed("/path/to/.rgignore")

# System handles:
# - Reloading affected files
# - Invalidating relevant caches
# - Updating rule hierarchy
```

#### 4. Watchdog-Ready Interface

```python
# Usage with external watchdog
class ExternalWatcher:
    def __init__(self, ignore_manager):
        self.ignore_manager = ignore_manager
        
    def on_file_changed(self, path):
        if path.endswith(ignore_manager.ignore_filename):
            self.ignore_manager.notify_file_changed(path)
```

## Detailed Design

### 1. IgnoreManager (Main API)

```python
from ignore.constants import IGNORE_FILENAME

class IgnoreManager:
    def __init__(self, 
                 root_path: Path,
                 default_patterns: List[str] = None,
                 cache_size: int = 10000):
        """
        Initialize the ignore manager
        
        Args:
            root_path: Root directory to manage
            default_patterns: Global default exclusions
            cache_size: LRU cache size for path decisions
        """
        self.ignore_filename = IGNORE_FILENAME
        self._registry = IgnoreFileRegistry()
        self._rule_engine = IgnoreRuleEngine()
        self._cache = IgnoreCache(cache_size)
        self._load_ignore_files()
        
    def should_ignore(self, path: Union[str, Path]) -> bool:
        """Check if path should be ignored"""
        
    def notify_file_changed(self, file_path: Union[str, Path]):
        """Handle external notification of ignore file change"""
        
    def reload_file(self, file_path: Union[str, Path]):
        """Reload specific ignore file and update rules"""
        
    def get_patterns_for_path(self, path: Union[str, Path]) -> List[str]:
        """Get all patterns affecting a path"""
        
    def validate_all(self) -> Dict[str, ValidationReport]:
        """Validate all ignore files"""
        
    def get_ignore_files(self) -> List[Path]:
        """Get list of all discovered ignore files"""
```

### 2. IgnoreRuleEngine

```python
class IgnoreRuleEngine:
    def compile_rules(self, rules_by_level: Dict[Path, List[str]]) -> CompiledRules:
        """Compile multi-level rules into efficient matcher"""
        
    def match_path(self, path: Path, compiled_rules: CompiledRules) -> MatchResult:
        """Match path against compiled rules with precedence"""
```

### 3. IgnoreFileRegistry

```python
class IgnoreFileRegistry:
    def __init__(self):
        self._files: Dict[Path, IgnoreFileInfo] = {}
        self._hierarchy: Dict[Path, List[Path]] = {}
        
    def register_file(self, file_path: Path, patterns: List[str]):
        """Register an ignore file and its patterns"""
        
    def unregister_file(self, file_path: Path):
        """Remove an ignore file from registry"""
        
    def get_files_for_path(self, path: Path) -> List[Path]:
        """Get all ignore files that affect a given path"""
        
    def get_file_info(self, file_path: Path) -> Optional[IgnoreFileInfo]:
        """Get information about a registered ignore file"""
```

### 4. IgnoreCache

```python
class IgnoreCache:
    def __init__(self, max_size: int = 10000):
        self._path_cache = LRUCache(max_size)
        self._pattern_cache = {}
        
    def get_decision(self, path: Path) -> Optional[bool]:
        """Get cached ignore decision"""
        
    def invalidate_path(self, path: Path):
        """Invalidate cache for path and descendants"""
```

## Implementation Phases

### Phase 1: Central Configuration & Core Refactoring (1-2 days)
1. Create `ignore/constants.py` with `IGNORE_FILENAME`
2. Extract pattern matching logic into `IgnoreRuleEngine`
3. Create `IgnoreFileLoader` for parsing and validation
4. Implement basic `IgnoreManager` with reload capability
5. Add comprehensive unit tests

### Phase 2: Multi-Level Support (2-3 days)
1. Implement directory traversal for ignore file discovery
2. Create `IgnoreFileRegistry` for tracking files
3. Add rule precedence and merging logic
4. Implement negation pattern support
5. Test with complex directory structures

### Phase 3: External Change Notification (1-2 days)
1. Implement `notify_file_changed` method
2. Add selective file reloading
3. Implement cache invalidation strategies
4. Test rapid change scenarios

### Phase 4: Performance Optimization (1-2 days)
1. Implement LRU cache for path decisions
2. Add pattern compilation cache
3. Optimize rule matching algorithm
4. Add performance benchmarks

### Phase 5: Integration & Migration (1 day)
1. Update existing `PatternMatcher` to use new system
2. Create migration guide
3. Update documentation
4. Create example watchdog integration

## API Examples

### Basic Usage

```python
from mcp_ragex.ignore import IgnoreManager

# Initialize
ignore_manager = IgnoreManager(
    root_path="/path/to/project"
)

# Check if file should be ignored
if not ignore_manager.should_ignore("/path/to/project/src/main.py"):
    process_file()

# Handle external change notification
ignore_manager.notify_file_changed("/path/to/project/.rgignore")

# Get the configured ignore filename
print(f"Using ignore file: {ignore_manager.ignore_filename}")
```

### External Watchdog Integration

```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from mcp_ragex.ignore import IgnoreManager

class IgnoreAwareHandler(FileSystemEventHandler):
    def __init__(self, ignore_manager: IgnoreManager):
        self.ignore_manager = ignore_manager
        
    def on_any_event(self, event):
        # Notify ignore manager of changes to ignore files
        if event.src_path.endswith(self.ignore_manager.ignore_filename):
            self.ignore_manager.notify_file_changed(event.src_path)
            return
            
        # Use ignore manager for filtering
        if not self.ignore_manager.should_ignore(event.src_path):
            self.process_event(event)
            
    def process_event(self, event):
        # Handle non-ignored files
        pass

# Setup
ignore_manager = IgnoreManager("/path/to/project")
handler = IgnoreAwareHandler(ignore_manager)
observer = Observer()
observer.schedule(handler, "/path/to/project", recursive=True)
observer.start()
```

### Advanced Configuration

```python
# Custom default patterns
ignore_manager = IgnoreManager(
    root_path="/path/to/project",
    default_patterns=[
        "*.pyc",
        "__pycache__/",
        ".git/",
        "node_modules/",
        "*.log"
    ],
    cache_size=50000  # Large project
)

# Get all discovered ignore files
ignore_files = ignore_manager.get_ignore_files()
print(f"Found {len(ignore_files)} ignore files:")
for file in ignore_files:
    print(f"  - {file}")

# Get validation report
report = ignore_manager.validate_all()
for file_path, validation in report.items():
    if validation.has_errors():
        print(f"Errors in {file_path}:")
        for error in validation.errors:
            print(f"  Line {error.line}: {error.message}")

# Handle batch changes
for changed_file in changed_ignore_files:
    ignore_manager.notify_file_changed(changed_file)
```

### Future Migration to .ragexignore

```python
# Change is centralized in one place:
# In ignore/constants.py:
IGNORE_FILENAME = ".ragexignore"  # Changed from ".rgignore"

# All code automatically uses new filename
# No other changes needed!
```

## Migration Strategy

### From Current PatternMatcher

```python
# Old way
from pattern_matcher import PatternMatcher
matcher = PatternMatcher()
if matcher.should_exclude(file_path):
    skip_file()

# New way
from mcp_ragex.ignore import IgnoreManager
ignore_manager = IgnoreManager(Path.cwd())
if ignore_manager.should_ignore(file_path):
    skip_file()
```

### Backward Compatibility

- Provide `PatternMatcher` wrapper using new system
- Support single-file mode for simple use cases
- Maintain existing ripgrep integration

## Testing Strategy

### Unit Tests
- Pattern compilation and matching
- Multi-level precedence rules
- Cache behavior
- File watching events

### Integration Tests
- Complex directory structures
- Concurrent file operations
- Performance benchmarks
- Memory usage monitoring

### Example Test Cases

```python
def test_multi_level_precedence():
    """Test that deeper .rgignore files override parent rules"""
    
def test_hot_reload_debouncing():
    """Test that rapid changes are debounced properly"""
    
def test_negation_patterns():
    """Test that !patterns correctly re-include files"""
    
def test_cache_invalidation():
    """Test that cache is properly invalidated on rule changes"""
```

## Performance Considerations

### Optimizations
1. **Lazy Loading**: Only load ignore files when needed
2. **Incremental Updates**: Only recompile changed rule sets
3. **Path Caching**: Cache ignore decisions with LRU eviction
4. **Batch Notifications**: Handle multiple file changes efficiently
5. **Compiled Pattern Reuse**: Share compiled patterns across files

### Benchmarks
- Target: < 1ms per path check (cached)
- Target: < 10ms per path check (uncached)
- Target: < 50ms for single file reload
- Target: < 500ms for full reload of 100 ignore files

## Security Considerations

1. **Path Traversal**: Validate all paths stay within root
2. **Pattern Validation**: Prevent malicious patterns
3. **Resource Limits**: Cap number of patterns per file
4. **File Size Limits**: Limit .rgignore file sizes

## Future Enhancements

1. **Global .rgignore**: Support for user-level ignore files
2. **Pattern Templates**: Named pattern groups for reuse
3. **Performance Profiling**: Built-in profiling tools
4. **IDE Integration**: Plugins for VS Code, PyCharm
5. **Distributed Caching**: Share compiled patterns across processes

## Conclusion

This design provides a robust, performant, and extensible system for handling ignore patterns in Python projects. The modular architecture allows for easy testing, maintenance, and future enhancements while maintaining backward compatibility with existing code.
