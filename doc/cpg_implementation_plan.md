# Code Property Graph Implementation Plan for RAGex MCP

## Executive Summary

This plan outlines the implementation of a lightweight Code Property Graph (CPG) to enhance semantic search capabilities. The CPG will capture code relationships (imports, calls, data flow) that are currently invisible to the vector embedding approach.

## Goals

1. **Primary**: Enable relationship-aware code search ("find all code using environment variable X")
2. **Secondary**: Support impact analysis ("what breaks if I change function Y")
3. **Tertiary**: Enable architectural insights ("show me the authentication flow")

## Architecture Overview

```
Current:
Tree-sitter → Symbols → Embeddings → ChromaDB → Search Results

Enhanced:
Tree-sitter → AST → CPG Builder → Graph DB ←→ ChromaDB → Hybrid Search
                           ↓
                    Relationship Edges
```

## Phase 1: Foundation (Week 1-2)

### 1.1 CPG Schema Design

Define core node types and relationships:

```python
# Node Types
class CPGNodeType(Enum):
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    VARIABLE = "variable"
    IMPORT = "import"
    CONSTANT = "constant"
    CONFIG = "config"  # Special type for env vars/settings

# Edge Types  
class CPGEdgeType(Enum):
    # Structural
    CONTAINS = "contains"        # Module contains class/function
    DEFINES = "defines"          # Function defines variable
    
    # Dependencies
    IMPORTS = "imports"          # Module imports module
    USES = "uses"               # Function uses variable/class
    CALLS = "calls"             # Function calls function
    EXTENDS = "extends"         # Class inheritance
    
    # Data flow
    ASSIGNS = "assigns"         # Variable assignment
    READS = "reads"            # Read variable value
    FLOWS_TO = "flows_to"      # Data flow tracking
```

### 1.2 Basic CPG Builder

Create a CPG builder that works with Tree-sitter output:

```python
# src/cpg_builder.py
class CPGBuilder:
    def __init__(self, tree_sitter_enhancer):
        self.enhancer = tree_sitter_enhancer
        self.nodes = []
        self.edges = []
    
    def build_from_file(self, file_path: str) -> CPGraph:
        # Parse with Tree-sitter
        tree = self.enhancer.parse_file(file_path)
        
        # Extract nodes
        self.extract_nodes(tree)
        
        # Build relationships
        self.build_import_edges()
        self.build_call_edges()
        self.build_containment_edges()
        
        return CPGraph(self.nodes, self.edges)
```

### 1.3 Import Resolution

Implement Python import resolution:

```python
class ImportResolver:
    def resolve_import(self, import_stmt: str, current_file: str) -> str:
        """
        Resolve 'from .module import func' to actual file path
        """
        # Handle relative imports
        # Handle package imports
        # Handle stdlib detection
        return resolved_path
```

## Phase 2: Core Relationships (Week 3-4)

### 2.1 Call Graph Construction

Build function call relationships:

```python
class CallGraphBuilder:
    def extract_calls(self, function_ast):
        """
        Find all function calls within a function body
        """
        calls = []
        for node in ast.walk(function_ast):
            if node.type == "call":
                called_name = self.extract_call_name(node)
                calls.append({
                    "from": function_ast.name,
                    "to": called_name,
                    "line": node.line
                })
        return calls
```

### 2.2 Variable Usage Tracking

Track variable definitions and usage:

```python
class DataFlowAnalyzer:
    def analyze_function(self, func_ast):
        # Track variable assignments
        assignments = self.find_assignments(func_ast)
        
        # Track variable reads
        reads = self.find_reads(func_ast)
        
        # Special handling for environment variables
        env_vars = self.find_env_vars(func_ast)
        
        return self.build_flow_edges(assignments, reads, env_vars)
```

### 2.3 Configuration Detection

Special handling for configuration patterns:

```python
class ConfigDetector:
    PATTERNS = [
        r"os\.environ\.get\(['\"](.*?)['\"]\)",
        r"os\.getenv\(['\"](.*?)['\"]\)",
        r"config\[['\"](.*?)['\"]\]",
        r"settings\.(\w+)"
    ]
    
    def find_config_access(self, code: str) -> List[ConfigAccess]:
        # Detect environment variables
        # Detect config file access
        # Detect settings objects
        return config_accesses
```

## Phase 3: Storage Layer (Week 5-6)

### 3.1 Graph Storage Options

**Option A: Embedded Graph DB (Recommended for start)**
```python
# Using NetworkX for in-memory graph
import networkx as nx
import pickle

class EmbeddedGraphStore:
    def __init__(self, persist_path: str):
        self.graph = nx.DiGraph()
        self.persist_path = persist_path
    
    def add_node(self, node_id: str, **attributes):
        self.graph.add_node(node_id, **attributes)
    
    def add_edge(self, from_id: str, to_id: str, edge_type: str):
        self.graph.add_edge(from_id, to_id, type=edge_type)
    
    def save(self):
        with open(self.persist_path, 'wb') as f:
            pickle.dump(self.graph, f)
```

**Option B: Neo4j (For production)**
```python
from neo4j import GraphDatabase

class Neo4jGraphStore:
    def __init__(self, uri: str, auth: tuple):
        self.driver = GraphDatabase.driver(uri, auth=auth)
    
    def add_node(self, node_id: str, node_type: str, **props):
        query = """
        MERGE (n:CodeElement {id: $id})
        SET n.type = $type, n += $props
        """
        # Execute query
```

### 3.2 Graph-Vector DB Synchronization

Keep CPG and ChromaDB in sync:

```python
class HybridIndexer:
    def __init__(self, vector_store, graph_store):
        self.vector_store = vector_store
        self.graph_store = graph_store
    
    def index_symbol(self, symbol):
        # Add to vector store with embedding
        vec_id = self.vector_store.add(symbol)
        
        # Add to graph with relationships
        graph_id = self.graph_store.add_node(symbol)
        
        # Store mapping
        self.id_mapping[vec_id] = graph_id
```

## Phase 4: Hybrid Search (Week 7-8)

### 4.1 Query Planner

Determine optimal search strategy:

```python
class QueryPlanner:
    def plan_search(self, query: str) -> SearchPlan:
        # Analyze query intent
        if self.is_relationship_query(query):
            return GraphFirstPlan()
        elif self.is_semantic_query(query):
            return VectorFirstPlan()
        else:
            return HybridPlan()
```

### 4.2 Graph-Enhanced Search

Combine vector and graph search:

```python
class HybridSearcher:
    def search(self, query: str) -> List[SearchResult]:
        # Step 1: Vector search for initial candidates
        vector_results = self.vector_search(query, limit=20)
        
        # Step 2: Graph expansion
        expanded_results = []
        for result in vector_results:
            # Find related nodes through graph
            related = self.graph_store.find_related(
                result.id, 
                edge_types=["CALLS", "USES", "IMPORTS"],
                max_depth=2
            )
            expanded_results.extend(related)
        
        # Step 3: Re-rank using graph metrics
        return self.rank_results(expanded_results)
```

### 4.3 Relationship Queries

Enable direct relationship queries:

```python
class RelationshipSearcher:
    def search_relationships(self, query: dict) -> List[Edge]:
        """
        Example query:
        {
            "from_type": "function",
            "edge_type": "CALLS",
            "to_name_pattern": "validate.*"
        }
        """
        return self.graph_store.query_edges(query)
```

## Phase 5: Enhanced Features (Week 9-10)

### 5.1 Impact Analysis

```python
class ImpactAnalyzer:
    def analyze_change_impact(self, changed_element: str):
        # Find all dependents
        dependents = self.graph_store.traverse(
            start=changed_element,
            direction="incoming",
            edge_types=["CALLS", "USES", "IMPORTS"]
        )
        
        # Categorize by impact level
        return {
            "direct": dependents[:1],
            "indirect": dependents[1:],
            "tests": [d for d in dependents if "test" in d.file]
        }
```

### 5.2 Flow Visualization

```python
class FlowAnalyzer:
    def trace_execution_flow(self, entry_point: str):
        # Build execution paths
        paths = self.graph_store.find_all_paths(
            start=entry_point,
            edge_type="CALLS",
            max_length=10
        )
        
        # Generate flow diagram
        return self.visualize_paths(paths)
```

### 5.3 Architecture Insights

```python
class ArchitectureAnalyzer:
    def find_architectural_patterns(self):
        # Detect circular dependencies
        cycles = self.graph_store.find_cycles()
        
        # Find god classes/modules
        hubs = self.graph_store.find_hubs(threshold=20)
        
        # Identify layers
        layers = self.detect_layers()
        
        return ArchitectureReport(cycles, hubs, layers)
```

## Implementation Timeline

### Week 1-2: Foundation
- [ ] Design CPG schema
- [ ] Implement basic CPG builder
- [ ] Create import resolver

### Week 3-4: Core Relationships  
- [ ] Build call graph extractor
- [ ] Implement data flow analysis
- [ ] Add configuration detection

### Week 5-6: Storage
- [ ] Implement embedded graph store
- [ ] Add persistence layer
- [ ] Create sync mechanism

### Week 7-8: Search Integration
- [ ] Build query planner
- [ ] Implement hybrid search
- [ ] Add relationship queries

### Week 9-10: Advanced Features
- [ ] Add impact analysis
- [ ] Create flow visualization
- [ ] Build architecture insights

## Success Metrics

1. **Functionality**
   - Can find all usages of an environment variable
   - Can trace function call chains
   - Can identify configuration dependencies

2. **Performance**
   - CPG build time < 30s for 1000 files
   - Query response time < 200ms
   - Incremental update < 2s per file

3. **Accuracy**
   - 95% accurate import resolution
   - 90% accurate call graph
   - 100% accurate for direct dependencies

## Risk Mitigation

1. **Scalability**: Start with embedded graph, migrate to Neo4j if needed
2. **Complexity**: Focus on Python first, add languages incrementally
3. **Performance**: Use caching and incremental updates
4. **Maintenance**: Clear separation between AST parsing and graph building

## Next Steps

1. Prototype the CPG builder with a simple Python file
2. Test import resolution accuracy
3. Benchmark graph storage options
4. Design the hybrid search API

This phased approach allows us to deliver value incrementally while building toward a comprehensive code intelligence system.