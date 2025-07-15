# Code Property Graph for Enhanced Semantic Search

## What is a Code Property Graph (CPG)?

A Code Property Graph combines three traditional program representations:
- **Abstract Syntax Tree (AST)**: Syntactic structure
- **Control Flow Graph (CFG)**: Execution paths
- **Program Dependence Graph (PDG)**: Data and control dependencies

This creates a unified graph where nodes represent code elements and edges represent various relationships (syntax, control flow, data flow).

## Current Architecture vs CPG-Enhanced Architecture

### Current: Tree-sitter + Vector Embeddings
```
Source Code → Tree-sitter AST → Symbol Extraction → Embeddings → ChromaDB
```

**Limitations:**
- Only captures syntactic structure
- No understanding of how code elements relate
- Can't track data flow or dependencies
- Misses runtime relationships

### Enhanced: Tree-sitter + CPG + Embeddings
```
Source Code → Tree-sitter AST → CPG Construction → Rich Graph → Embeddings → ChromaDB
                                         ↓
                                  Graph Database (Neo4j)
```

## How CPG Enhances Semantic Search

### 1. **Dependency Tracking**

**Current Limitation:**
```python
# File: auth.py
def validate_token(token):
    return check_signature(token)  # Where is check_signature defined?

# File: crypto.py  
def check_signature(data):
    return hmac.verify(data)
```
Search for "token validation" finds `validate_token` but not `check_signature`.

**With CPG:**
- Creates edges: `validate_token` --calls--> `check_signature`
- Search traverses graph to find related functions
- Results include full call chain

### 2. **Data Flow Analysis**

**Current Limitation:**
```python
# Can't track where environment variables are used
API_KEY = os.environ.get('API_KEY')  # Line 10

def make_request():
    headers = {'Authorization': API_KEY}  # Line 50
```

**With CPG:**
- Creates edges: `API_KEY` --flows-to--> `headers`
- Search for "environment variable usage" finds both definition and all usage sites
- Can answer: "What code is affected by API_KEY?"

### 3. **Type and Interface Relationships**

**Current Limitation:**
```python
class UserService:
    def get_user(self, id: int) -> User:
        pass

class AuthService:
    def __init__(self, user_service: UserService):
        self.user_service = user_service
```

**With CPG:**
- Creates edges: `AuthService` --depends-on--> `UserService`
- Search for "services using User model" finds complete dependency chain
- Enables architectural queries: "What depends on UserService?"

## Integration with Tree-sitter

### Phase 1: AST Enhancement
```python
# Tree-sitter provides AST
ast = tree_sitter.parse(source_code)

# Enhance with semantic information
cpg_builder = CPGBuilder(ast)
cpg_builder.add_type_information()  # From type hints/inference
cpg_builder.add_import_resolution()  # Resolve import paths
cpg_builder.add_symbol_tables()      # Variable/function scopes
```

### Phase 2: Control Flow Construction
```python
# Build CFG from AST
cfg = ControlFlowBuilder(ast)
cfg.add_basic_blocks()
cfg.add_edges()  # Sequential, conditional, loop edges
cfg.handle_exceptions()  # Try-catch flow
```

### Phase 3: Data Flow Analysis
```python
# Track data dependencies
dfa = DataFlowAnalyzer(ast, cfg)
dfa.track_variable_definitions()
dfa.track_variable_uses()
dfa.build_def_use_chains()
```

## Example CPG-Powered Queries

### 1. **Impact Analysis**
"What code is affected if I change the `User` model?"
```cypher
MATCH (n:Class {name: 'User'})<-[:USES|EXTENDS|RETURNS*]-(affected)
RETURN affected
```

### 2. **Security Analysis**
"Find all paths from user input to database queries"
```cypher
MATCH path = (input:Parameter)-[:FLOWS_TO*]->(query:DatabaseCall)
WHERE input.source = 'user_input'
RETURN path
```

### 3. **Architectural Queries**
"Find circular dependencies"
```cypher
MATCH (a)-[:DEPENDS_ON*]->(b)-[:DEPENDS_ON*]->(a)
RETURN DISTINCT a, b
```

## Semantic Search Enhancement

### Current Search
Query: "authentication flow"
Result: Functions with "auth" in name

### CPG-Enhanced Search
Query: "authentication flow"
Result: 
1. Entry points (`login`, `authenticate`)
2. Validation functions (via control flow)
3. Token generation (via data flow)
4. Database queries (via dependencies)
5. Error handling paths

## Implementation Approach

### 1. **Lightweight CPG for Search**
- Focus on call graphs and import dependencies
- Store in graph database (Neo4j) alongside ChromaDB
- Use for relationship queries

### 2. **Hybrid Queries**
```python
# Step 1: Semantic search in ChromaDB
candidates = vector_search("authentication logic")

# Step 2: Graph expansion in Neo4j
expanded_results = []
for candidate in candidates:
    # Find related code through CPG
    related = graph.query(f"""
        MATCH (n {{id: '{candidate.id}'}})-[:CALLS|USES|DEPENDS_ON*..2]-(related)
        RETURN related
    """)
    expanded_results.extend(related)

# Step 3: Re-rank based on graph centrality
return rank_by_importance(expanded_results)
```

### 3. **Graph-Aware Embeddings**
```python
def create_enhanced_embedding(node, cpg):
    # Original code embedding
    code_embedding = embed_text(node.code)
    
    # Context from graph
    neighbors = cpg.get_neighbors(node, max_depth=2)
    context_text = " ".join([n.name for n in neighbors])
    context_embedding = embed_text(context_text)
    
    # Combine embeddings
    return combine_embeddings(code_embedding, context_embedding)
```

## Benefits for Specific Use Cases

### 1. **Configuration Discovery**
- Track environment variable flow through the codebase
- Find all configuration consumers
- Identify configuration validation points

### 2. **API Understanding**
- Map request flow from entry point to response
- Find all middleware/interceptors
- Track authentication/authorization checks

### 3. **Refactoring Support**
- Find all usages accurately (not just text matches)
- Identify safe rename/move operations
- Detect dead code

## Challenges and Considerations

### 1. **Scalability**
- CPG construction is computationally expensive
- Graph can become very large for big codebases
- Need incremental update strategies

### 2. **Language Support**
- Different languages need different analysis
- Dynamic languages are harder to analyze
- May need runtime information

### 3. **Maintenance**
- CPG needs updates when code changes
- Sync between CPG and vector embeddings
- Version control for graph changes

## Recommendation

For CodeRAG MCP, implement a **lightweight CPG** focused on:
1. **Import/dependency graph** (immediate value, low cost)
2. **Call graph** (high value for understanding code flow)
3. **Basic data flow** (for configuration tracking)

Store the CPG in a graph database and use it to:
- Enhance search results with related code
- Answer relationship queries directly
- Improve embedding quality with graph context

This provides significant search improvements without the full complexity of a complete CPG implementation.