# Python Import Issue Analysis and Fix Plan

## Problem Summary

The warning "Tree-sitter enhancer disabled due to: attempted relative import with no known parent package" occurs when running `ragex search` command in the Docker container. This happens despite attempts to fix imports by setting PYTHONPATH.

## Root Cause Analysis

### 1. Import Chain
```
ragex_search.py 
  → imports from src.vector_store import CodeVectorStore
    → CodeVectorStore instantiation triggers
      → Some module imports src.indexer
        → indexer.py tries to create TreeSitterEnhancer() (line 71)
          → TreeSitterEnhancer.__init__ executes
            → Line 57: from pattern_matcher import PatternMatcher
              → This relative import fails!
```

### 2. The Core Issue

The problem stems from mixing import styles and Python path manipulations:

1. **PYTHONPATH in Docker**: Set to `/app:/app/src`
2. **ragex_search.py**: Imports using `from src.module import X`
3. **Inside src/ modules**: Some use absolute imports (`from src.X`), others use relative imports
4. **tree_sitter_enhancer.py**: Uses a delayed import `from pattern_matcher import PatternMatcher` inside `__init__`

When Python executes from `/app`, it can find `src.module` imports. But when code inside `src/` tries to do `from pattern_matcher import`, it fails because:
- The module's `__name__` is `src.tree_sitter_enhancer` 
- Python looks for `pattern_matcher` as a top-level module (not found)
- It's not a relative import (no leading dot), so it doesn't look in the same package

### 3. Why Previous Fixes Failed

1. **Setting PYTHONPATH=/app:/app/src**: This makes both paths searchable, but creates ambiguity
2. **Changing to `from src.pattern_matcher`**: Fails when inside src/ because there's no src/ inside src/
3. **Running as module (`python -m`)**: Helps with some imports but not all

## The Real Solution

We need to establish a consistent import strategy across the entire codebase:

### Option 1: Absolute Imports from Project Root (Recommended)

**Principle**: All imports use the full path from the project root (`src.module.Class`)

**Implementation**:
1. Set `PYTHONPATH=/app` only
2. All imports must use `from src.module import X` format
3. No relative imports anywhere
4. No sys.path manipulations

**Changes needed**:
- Fix tree_sitter_enhancer.py line 57: `from src.pattern_matcher import PatternMatcher`
- Fix all other relative imports in src/
- Remove all sys.path manipulations
- Ensure PYTHONPATH is only `/app`

### Option 2: Consistent Relative Imports

**Principle**: Use relative imports within packages

**Implementation**:
1. Use `from .module import X` for same-level imports
2. Use `from ..module import X` for parent-level imports
3. Run modules with `-m` flag: `python -m src.module`

**Changes needed**:
- Fix tree_sitter_enhancer.py line 57: `from .pattern_matcher import PatternMatcher`
- Update all imports in src/ to use relative imports
- Change execution to use module syntax

### Option 3: Package Installation

**Principle**: Install the package properly using pip

**Implementation**:
1. Add proper `__init__.py` files
2. Create setup.py or use pyproject.toml properly
3. Install with `pip install -e .` in Docker
4. Import as a proper package

## Recommended Fix Steps

1. **Immediate Fix** (Option 1):
   ```python
   # tree_sitter_enhancer.py line 57
   from src.pattern_matcher import PatternMatcher
   ```

2. **Update Dockerfile**:
   ```dockerfile
   ENV PYTHONPATH=/app
   ```

3. **Fix all imports to use absolute paths**:
   - All files in src/ should import as `from src.X import Y`
   - Remove all sys.path manipulations
   - No relative imports

4. **Update entrypoint.sh**:
   - Keep running as `python ragex_search.py` (not as module)
   - No need for complex path handling

5. **Test thoroughly**:
   - Test all commands: init, index, search, serve
   - Verify no import errors in logs
   - Check tree-sitter functionality works

## Long-term Improvements

1. **Standardize imports**: Create a coding standard document
2. **Use import linter**: Add `isort` or similar to CI/CD
3. **Proper packaging**: Consider making this a proper Python package
4. **Import tests**: Add tests that verify all imports work correctly

## Testing Plan

1. Build Docker image with fixes
2. Test each command:
   ```bash
   ragex init
   ragex index .
   ragex search "test"
   ragex serve
   ```
3. Check logs for any import warnings
4. Verify tree-sitter enhancer initializes properly