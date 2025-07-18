# Search Refactoring Plan

## Problem Statement

Currently, we have two implementations of code search:
1. **ragex_search.py**: Semantic search works perfectly (no similarity threshold filtering)
2. **MCP server (server.py)**: Regex/symbol search work, but semantic search returns 0 results due to overly strict similarity threshold (0.7)

The implementations have diverged, making maintenance difficult and behavior inconsistent.

## Solution: Unified Search Architecture

Create a base class architecture with specialized search implementations, allowing us to:
- Use the proven semantic search from ragex_search.py
- Use the proven regex/symbol search from MCP server
- Ensure consistent behavior between both tools
- Enable easy testing and maintenance

## Architecture Design

```
src/
├── search/
│   ├── __init__.py
│   ├── base.py          # Abstract base class
│   ├── regex.py         # Regex search implementation
│   ├── symbol.py        # Symbol search implementation  
│   ├── semantic.py      # Semantic search implementation
│   └── unified.py       # Unified searcher that combines all
```

### Base Class (search/base.py)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

@dataclass
class SearchResult:
    file: str
    line_number: int
    line: str
    type: Optional[str] = None
    name: Optional[str] = None
    similarity: Optional[float] = None
    code: Optional[str] = None

class SearchBase(ABC):
    """Abstract base class for all search implementations"""
    
    @abstractmethod
    async def search(
        self, 
        query: str, 
        limit: int = 50,
        file_types: Optional[List[str]] = None,
        paths: Optional[List[str]] = None,
        **kwargs
    ) -> List[SearchResult]:
        """Execute search and return results"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this search method is available"""
        pass
```

### Implementation Classes

1. **SearchRegex** (from MCP server)
   - Move RipgrepSearcher functionality
   - Keep all validation and security features
   - Maintain JSON streaming for performance

2. **SearchSymbol** (from MCP server)
   - Currently uses ripgrep with word boundaries
   - Could be enhanced with Tree-sitter AST search

3. **SearchSemantic** (from ragex_search.py)
   - Move semantic search logic from SearchClient
   - Remove similarity threshold filtering (or make configurable)
   - Keep deduplication logic

### Unified Searcher (search/unified.py)

```python
class UnifiedSearcher:
    def __init__(self, index_dir: Optional[str] = None):
        self.searchers = {
            'regex': SearchRegex(),
            'symbol': SearchSymbol(),
            'semantic': SearchSemantic(index_dir=index_dir)
        }
    
    async def search(self, query: str, mode: str = 'auto', **kwargs) -> List[SearchResult]:
        if mode == 'auto':
            mode = self.detect_mode(query)
        
        searcher = self.searchers.get(mode)
        if not searcher or not searcher.is_available():
            # Fallback logic
            return await self.fallback_search(query, mode, **kwargs)
        
        return await searcher.search(query, **kwargs)
```

## Implementation Steps

### Phase 1: Create Base Architecture
1. Create `src/search/` directory structure
2. Implement `SearchBase` abstract class
3. Define `SearchResult` dataclass

### Phase 2: Extract Semantic Search
1. Copy semantic search logic from `ragex_search.py`
2. Create `SearchSemantic` class
3. Remove similarity threshold or make it configurable
4. Ensure it uses the correct ChromaDB path logic

### Phase 3: Extract Regex/Symbol Search
1. Move `RipgrepSearcher` to `SearchRegex` class
2. Create `SearchSymbol` class (initially wrapping regex)
3. Maintain all security validations

### Phase 4: Create Unified Searcher
1. Implement `UnifiedSearcher` with mode detection
2. Add fallback logic between search modes
3. Ensure consistent result formatting

### Phase 5: Update Existing Tools
1. Update `ragex_search.py` to use `UnifiedSearcher`
2. Update `server.py` to use `UnifiedSearcher`
3. Ensure both pass correct parameters (index_dir, etc.)

### Phase 6: Testing & Validation
1. Create unit tests for each search class
2. Test that ragex_search.py still works identically
3. Test that MCP server now returns semantic results
4. Verify all three search modes work in both tools

## Benefits

1. **Single source of truth**: Each search type has one implementation
2. **Proven code**: We keep what works from each tool
3. **Easier testing**: Each search type can be tested independently
4. **Better maintenance**: Bug fixes apply to both tools automatically
5. **Extensibility**: Easy to add new search types (AST, fuzzy, etc.)
6. **Consistent behavior**: Both tools behave identically

## Risks & Mitigations

1. **Risk**: Breaking existing functionality
   - **Mitigation**: Extensive testing, gradual migration

2. **Risk**: Performance regression
   - **Mitigation**: Keep existing optimizations, profile before/after

3. **Risk**: API compatibility
   - **Mitigation**: Maintain existing APIs, adapt internally

## Success Criteria

1. ragex_search.py semantic search continues to work identically
2. MCP server semantic search returns results (fixes threshold issue)
3. All three search modes work in both tools
4. Code is more maintainable with clear separation of concerns
5. Performance remains the same or improves