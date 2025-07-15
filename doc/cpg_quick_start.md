# CPG Quick Start - Minimum Viable Implementation

## Problem We're Solving

Current semantic search can't find:
- `OPENSEARCH_URL = os.environ.get('OPENSEARCH_URL')` (module-level code)
- Which functions use this environment variable
- What breaks if we change this configuration

## Minimal CPG Solution

### Step 1: Extend Tree-sitter Extraction (2 days)

```python
# Add to tree_sitter_enhancer.py
def extract_module_level_code(self, tree):
    """Extract imports, constants, and config at module level"""
    
    # Extract imports
    imports = []
    for node in tree.root_node.children:
        if node.type == "import_statement":
            imports.append({
                "type": "import",
                "name": self.get_import_name(node),
                "line": node.start_point[0]
            })
    
    # Extract module-level assignments
    assignments = []
    for node in tree.root_node.children:
        if node.type == "assignment":
            # Check if it's reading environment
            if "environ" in node.text.decode():
                assignments.append({
                    "type": "config",
                    "name": self.get_var_name(node),
                    "value": node.text.decode(),
                    "line": node.start_point[0]
                })
    
    return imports + assignments
```

### Step 2: Simple Relationship Tracking (2 days)

```python
# New file: src/relationship_tracker.py
class RelationshipTracker:
    def __init__(self):
        self.relationships = {
            "defines": {},      # module -> [variables]
            "uses": {},         # function -> [variables]
            "calls": {},        # function -> [functions]
            "imports": {}       # module -> [modules]
        }
    
    def add_definition(self, module: str, var_name: str):
        if module not in self.relationships["defines"]:
            self.relationships["defines"][module] = []
        self.relationships["defines"][module].append(var_name)
    
    def find_usage(self, var_name: str) -> List[str]:
        """Find all functions using a variable"""
        usages = []
        for func, vars in self.relationships["uses"].items():
            if var_name in vars:
                usages.append(func)
        return usages
```

### Step 3: Enhanced Indexing (1 day)

```python
# Modify indexer.py
def index_with_relationships(self, file_path):
    # Current: Extract symbols
    symbols = self.extract_symbols(file_path)
    
    # New: Extract module-level code
    module_code = self.extract_module_level_code(file_path)
    
    # New: Track relationships
    relationships = self.build_relationships(symbols, module_code)
    
    # Store both in vector DB with metadata
    for item in module_code:
        self.vector_store.add({
            **item,
            "file": file_path,
            "related_functions": relationships.get(item["name"], [])
        })
```

### Step 4: Relationship-Aware Search (2 days)

```python
# Add to server.py
async def search_with_relationships(self, query: str):
    # Step 1: Find initial matches
    matches = await self.semantic_search(query)
    
    # Step 2: Expand through relationships
    expanded = []
    for match in matches:
        if match.type == "config":
            # Find all functions using this config
            users = self.relationships.find_usage(match.name)
            expanded.extend(users)
    
    # Step 3: Return enriched results
    return {
        "direct_matches": matches,
        "related_code": expanded,
        "relationship_type": "uses_config"
    }
```

## Immediate Benefits

1. **Find Environment Variables**
   ```
   Query: "OPENSEARCH_URL configuration"
   Returns:
   - Line 23: OPENSEARCH_URL = os.environ.get(...)
   - Used by: make_request() at line 145
   - Used by: check_connection() at line 203
   ```

2. **Configuration Impact**
   ```
   Query: "what uses SCAN_INTERVAL"
   Returns:
   - Definition: line 316
   - Used in: main() monitoring loop
   - Type: environment variable
   - Default: 300
   ```

3. **Import Dependencies**
   ```
   Query: "files importing Environment"
   Returns:
   - monitor.py imports from shared.config.environment
   - Used to read: excluded_directories, scan_interval
   ```

## Storage Options (Choose One)

### Option A: Extend ChromaDB Metadata (Fastest)
```python
# Store relationships in metadata
vector_store.add(
    embeddings=[embedding],
    metadatas=[{
        "type": "config",
        "name": "OPENSEARCH_URL",
        "defined_in": "monitor.py:23",
        "used_by": ["make_request:145", "check_connection:203"],
        "imports": ["os", "environ"]
    }]
)
```

### Option B: Simple JSON Graph (Simple)
```python
# Store as graph.json alongside chroma_db
{
    "nodes": {
        "monitor.py:OPENSEARCH_URL": {
            "type": "config",
            "line": 23
        }
    },
    "edges": [
        {
            "from": "monitor.py:OPENSEARCH_URL",
            "to": "monitor.py:make_request",
            "type": "used_by"
        }
    ]
}
```

## Implementation Priority

1. **Day 1-2**: Extract module-level code (imports, configs)
2. **Day 3-4**: Track basic relationships (defines, uses)
3. **Day 5**: Store relationships with vector embeddings
4. **Day 6-7**: Implement relationship-aware search

## Why This Works

- **Minimal changes**: Extends existing Tree-sitter code
- **Immediate value**: Solves the environment variable problem
- **Incremental**: Can add more relationship types later
- **Compatible**: Works with current vector search

This gives us 80% of CPG benefits with 20% of the complexity.