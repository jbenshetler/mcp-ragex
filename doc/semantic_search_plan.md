# Semantic Code Search Implementation Plan

## Overview

Build a semantic search system for the MCP code search server that enables natural language queries like "functions that submit files to the celery queue". Start with sentence-transformers for quick implementation, with a clear upgrade path to CodeBERT for better code understanding.

## Goals

1. **Enable natural language search**: Find code by describing what it does, not just keyword matching
2. **Maintain fast performance**: Sub-second search results for 200+ file codebases
3. **Provide upgrade path**: Start simple, enhance with better models as needed
4. **Integrate seamlessly**: Add to existing MCP server without breaking current functionality

## Architecture Design

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   MCP Client    │────▶│   MCP Server     │────▶│ Search Engine   │
│ (Claude Code)   │     │                  │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                │                         │
                                ▼                         ▼
                        ┌──────────────────┐     ┌─────────────────┐
                        │ Ripgrep (exact)  │     │ Vector Search   │
                        └──────────────────┘     │   (semantic)    │
                                                 └─────────────────┘
                                                         │
                                                         ▼
                                                 ┌─────────────────┐
                                                 │   ChromaDB      │
                                                 │ (Vector Store)  │
                                                 └─────────────────┘
```

## Phase 1: Sentence-Transformers Foundation (Week 1)

### 1.1 Create Embedding System

**File: `src/embedding_manager.py`**

```python
class EmbeddingManager:
    def __init__(self, model_name="sentence-transformers/all-mpnet-base-v2"):
        self.model = SentenceTransformer(model_name)
        self.embedding_dim = 768  # for mpnet
    
    def create_code_context(self, symbol: Symbol) -> str:
        """Create enriched text representation of code"""
        # Combine multiple signals for better embedding
        return f"""
        Type: {symbol.type}
        Name: {symbol.name}
        File: {symbol.file}
        Signature: {symbol.signature}
        Documentation: {symbol.docstring}
        Parent: {symbol.parent}
        Language: {detected_language}
        Keywords: {extract_keywords(symbol.code)}
        Calls: {extract_function_calls(symbol.code)}
        Imports: {extract_imports(symbol.file)}
        """
    
    def embed_batch(self, texts: List[str]) -> np.ndarray:
        return self.model.encode(texts, batch_size=32, show_progress_bar=True)
```

**Key Design Decisions:**
- Use `all-mpnet-base-v2` for best quality/speed tradeoff
- Enrich code with metadata before embedding
- Batch processing for efficiency

### 1.2 Create Vector Store

**File: `src/vector_store.py`**

```python
class CodeVectorStore:
    def __init__(self, persist_directory="./chroma_db"):
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection(
            name="code_search",
            metadata={"hnsw:space": "cosine"}
        )
    
    def add_symbols(self, symbols: List[Symbol], embeddings: np.ndarray):
        # Store with metadata for filtering
        self.collection.add(
            embeddings=embeddings,
            documents=[s.code for s in symbols],
            metadatas=[{
                "type": s.type,
                "name": s.name,
                "file": s.file,
                "language": s.language,
                "parent": s.parent,
            } for s in symbols],
            ids=[f"{s.file}:{s.line}:{s.name}" for s in symbols]
        )
    
    def search(self, query_embedding: np.ndarray, limit: int = 20):
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            include=["metadatas", "documents", "distances"]
        )
        return results
```

**Why ChromaDB:**
- Simple embedded database (no server required)
- Persistent storage
- Good performance for <1M vectors
- Easy metadata filtering

### 1.3 Indexing Pipeline

**File: `src/indexer.py`**

```python
class CodeIndexer:
    def __init__(self):
        self.tree_sitter = TreeSitterEnhancer()
        self.embedder = EmbeddingManager()
        self.vector_store = CodeVectorStore()
        self.pattern_matcher = PatternMatcher()
    
    async def index_codebase(self, paths: List[str], force=False):
        # Check if index exists
        if not force and self.vector_store.collection.count() > 0:
            return {"status": "existing", "count": self.vector_store.collection.count()}
        
        # 1. Find all code files
        all_files = []
        for path in paths:
            files = find_code_files(path, self.pattern_matcher)
            all_files.extend(files)
        
        # 2. Extract symbols with progress
        all_symbols = []
        for file in tqdm(all_files, desc="Extracting symbols"):
            if self.pattern_matcher.should_exclude(file):
                continue
            symbols = await self.tree_sitter.extract_symbols(file)
            all_symbols.extend(symbols)
        
        # 3. Create context and embed
        texts = [self.embedder.create_code_context(s) for s in all_symbols]
        embeddings = self.embedder.embed_batch(texts)
        
        # 4. Store in vector database
        self.vector_store.add_symbols(all_symbols, embeddings)
        
        return {
            "status": "complete",
            "files_processed": len(all_files),
            "symbols_indexed": len(all_symbols)
        }
```

### 1.4 Hybrid Search Implementation

**File: `src/semantic_search.py`**

```python
class SemanticSearchEngine:
    def __init__(self):
        self.embedder = EmbeddingManager()
        self.vector_store = CodeVectorStore()
        self.ripgrep = RipgrepSearcher()
        self.query_enhancer = QueryEnhancer()
    
    async def search(
        self,
        query: str,
        limit: int = 20,
        file_types: Optional[List[str]] = None,
        threshold: float = 0.7,
        hybrid_mode: bool = True
    ):
        # 1. Enhance and embed query
        enhanced_query = self.query_enhancer.enhance(query)
        query_embedding = self.embedder.embed([enhanced_query])[0]
        
        # 2. Vector search
        vector_results = self.vector_store.search(
            query_embedding,
            limit=limit * 2 if hybrid_mode else limit
        )
        
        # 3. Optional: Ripgrep search for keywords
        keyword_results = []
        if hybrid_mode:
            keywords = extract_keywords(query)
            if keywords:
                pattern = "|".join(keywords)
                rg_results = await self.ripgrep.search(pattern, limit=limit)
                keyword_results = rg_results.get("matches", [])
        
        # 4. Merge and re-rank
        final_results = self.merge_and_rerank(
            vector_results, 
            keyword_results,
            limit,
            weights=[0.8, 0.2]  # Favor semantic results
        )
        
        return {
            "query": query,
            "enhanced_query": enhanced_query,
            "results": final_results,
            "search_type": "hybrid" if hybrid_mode else "semantic"
        }
```

## Phase 2: Pre-indexing Strategy

### 2.1 Standalone Indexing Script

Create a separate script that builds the index before starting the MCP server:

**File: `scripts/build_semantic_index.py`**

```python
#!/usr/bin/env python3
"""
Build semantic search index for the codebase.
Run this before starting the MCP server for the first time or when you need to rebuild the index.
"""

import asyncio
import sys
import time
from pathlib import Path
from datetime import datetime
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.indexer import CodeIndexer
from src.pattern_matcher import PatternMatcher
from tqdm import tqdm
import argparse

async def main():
    parser = argparse.ArgumentParser(description="Build semantic search index for code")
    parser.add_argument("paths", nargs="*", default=["."], 
                       help="Paths to index (default: current directory)")
    parser.add_argument("--force", action="store_true", 
                       help="Force rebuild even if index exists")
    parser.add_argument("--stats", action="store_true", 
                       help="Show detailed statistics after indexing")
    args = parser.parse_args()
    
    print("🔍 CodeRAG Semantic Search Indexer")
    print("=" * 50)
    
    # Check if index exists
    index_path = Path("./chroma_db")
    if index_path.exists() and not args.force:
        print("⚠️  Index already exists. Use --force to rebuild.")
        
        # Load and show existing index info
        metadata_path = index_path / "index_metadata.json"
        if metadata_path.exists():
            with open(metadata_path) as f:
                metadata = json.load(f)
            print(f"📊 Current index:")
            print(f"   - Created: {metadata['created_at']}")
            print(f"   - Symbols: {metadata['symbol_count']}")
            print(f"   - Files: {metadata['file_count']}")
        
        response = input("\nRebuild anyway? (y/N): ")
        if response.lower() != 'y':
            print("Aborted.")
            return
    
    # Initialize indexer
    print("\n📚 Initializing indexer...")
    indexer = CodeIndexer()
    
    # Count files first
    pattern_matcher = PatternMatcher()
    all_files = []
    for path in args.paths:
        for ext in ["py", "js", "jsx", "ts", "tsx"]:
            for file in Path(path).rglob(f"*.{ext}"):
                if not pattern_matcher.should_exclude(str(file)):
                    all_files.append(file)
    
    print(f"📁 Found {len(all_files)} files to index")
    
    if not all_files:
        print("❌ No files found to index!")
        return
    
    # Start indexing
    print("\n🏗️  Building index...")
    start_time = time.time()
    
    # Create custom progress callback
    progress_bar = tqdm(total=len(all_files), desc="Extracting symbols")
    processed_files = []
    
    async def progress_callback(file_path, status):
        progress_bar.update(1)
        if status == "success":
            processed_files.append(file_path)
    
    # Index with progress
    result = await indexer.index_codebase(
        paths=args.paths,
        force=True,
        progress_callback=progress_callback
    )
    
    progress_bar.close()
    elapsed = time.time() - start_time
    
    # Save metadata
    metadata = {
        "created_at": datetime.now().isoformat(),
        "paths": args.paths,
        "file_count": result["files_processed"],
        "symbol_count": result["symbols_indexed"],
        "index_time": elapsed,
        "excluded_patterns": pattern_matcher.patterns[:10]  # First 10 patterns
    }
    
    metadata_path = index_path / "index_metadata.json"
    metadata_path.parent.mkdir(exist_ok=True)
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    # Print summary
    print(f"\n✅ Indexing complete!")
    print(f"📊 Statistics:")
    print(f"   - Files processed: {result['files_processed']}")
    print(f"   - Symbols indexed: {result['symbols_indexed']}")
    print(f"   - Time taken: {elapsed:.1f}s")
    print(f"   - Symbols/second: {result['symbols_indexed']/elapsed:.1f}")
    print(f"   - Index location: {index_path.absolute()}")
    
    if args.stats and result['symbols_indexed'] > 0:
        print(f"\n📈 Detailed statistics:")
        # Add more detailed stats from indexer
        stats = await indexer.get_index_statistics()
        print(f"   - Functions: {stats.get('function_count', 0)}")
        print(f"   - Classes: {stats.get('class_count', 0)}")
        print(f"   - Methods: {stats.get('method_count', 0)}")
        print(f"   - Average symbol size: {stats.get('avg_symbol_size', 0):.0f} chars")
        print(f"   - Index size: {stats.get('index_size_mb', 0):.1f} MB")
    
    print(f"\n💡 Next steps:")
    print(f"   1. Start the MCP server: ./run_server.sh")
    print(f"   2. Use semantic_search in Claude Code")
    print(f"   3. Re-run this script when codebase changes significantly")

if __name__ == "__main__":
    asyncio.run(main())
```

### 2.2 Index Status Checking

Add utilities to check index status without rebuilding:

**File: `scripts/check_index.py`**

```python
#!/usr/bin/env python3
"""Check semantic search index status"""

import json
from pathlib import Path
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.vector_store import CodeVectorStore
from src.pattern_matcher import PatternMatcher

def main():
    index_path = Path("./chroma_db")
    
    if not index_path.exists():
        print("❌ No semantic search index found.")
        print("   Run: python scripts/build_semantic_index.py")
        return
    
    # Load metadata
    metadata_path = index_path / "index_metadata.json"
    if metadata_path.exists():
        with open(metadata_path) as f:
            metadata = json.load(f)
        
        # Calculate age
        created = datetime.fromisoformat(metadata['created_at'])
        age = datetime.now() - created
        
        print("📊 Semantic Search Index Status")
        print("=" * 50)
        print(f"✅ Index exists")
        print(f"📅 Created: {created.strftime('%Y-%m-%d %H:%M:%S')} ({age.days} days ago)")
        print(f"📁 Files indexed: {metadata['file_count']}")
        print(f"🔤 Symbols indexed: {metadata['symbol_count']}")
        print(f"⏱️  Index time: {metadata['index_time']:.1f}s")
        print(f"📍 Paths indexed: {', '.join(metadata['paths'])}")
        
        # Check for changes
        pattern_matcher = PatternMatcher()
        changed_files = []
        
        for path in metadata['paths']:
            for ext in ["py", "js", "jsx", "ts", "tsx"]:
                for file in Path(path).rglob(f"*.{ext}"):
                    if not pattern_matcher.should_exclude(str(file)):
                        # Simple check: compare modification time
                        if file.stat().st_mtime > created.timestamp():
                            changed_files.append(file)
        
        if changed_files:
            print(f"\n⚠️  {len(changed_files)} files changed since index was built:")
            for f in changed_files[:5]:
                print(f"   - {f}")
            if len(changed_files) > 5:
                print(f"   ... and {len(changed_files) - 5} more")
            print("\n💡 Consider rebuilding: python scripts/build_semantic_index.py --force")
        else:
            print("\n✅ Index is up to date")
    else:
        print("⚠️  Index exists but metadata is missing")

if __name__ == "__main__":
    main()
```

### 2.3 Integration with MCP Server

Update the MCP server to check for index on startup:

**Update: `src/server.py` initialization**

```python
# At server startup
def check_semantic_index():
    """Check if semantic index exists and log status"""
    index_path = Path("./chroma_db")
    if not index_path.exists():
        logger.warning(
            "Semantic search index not found. "
            "Run 'python scripts/build_semantic_index.py' to enable semantic search."
        )
        return False
    
    metadata_path = index_path / "index_metadata.json"
    if metadata_path.exists():
        with open(metadata_path) as f:
            metadata = json.load(f)
        logger.info(
            f"Semantic search index loaded: "
            f"{metadata['symbol_count']} symbols from {metadata['file_count']} files"
        )
        return True
    return False

# In server initialization
SEMANTIC_SEARCH_AVAILABLE = check_semantic_index()

# Update semantic_search tool to check availability
@app.tool()
async def semantic_search(query: str, ...) -> Dict:
    if not SEMANTIC_SEARCH_AVAILABLE:
        return {
            "error": "Semantic search not available",
            "message": "Index not found. Run: python scripts/build_semantic_index.py"
        }
    # ... rest of implementation
```

### 2.4 Automation Scripts

Create convenience scripts for common workflows:

**File: `scripts/setup_semantic_search.sh`**

```bash
#!/bin/bash
# One-time setup for semantic search

echo "🚀 Setting up semantic search..."

# Install additional dependencies
echo "📦 Installing dependencies..."
pip install -q sentence-transformers chromadb tqdm

# Build initial index
echo "🏗️  Building semantic search index..."
python scripts/build_semantic_index.py

echo "✅ Setup complete!"
```

**File: `scripts/update_index.py`**

```python
#!/usr/bin/env python3
"""Update semantic search index incrementally (for small changes)"""

import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.incremental_indexer import IncrementalIndexer

async def main():
    indexer = IncrementalIndexer()
    
    print("🔄 Checking for changes...")
    result = await indexer.update_changed_files()
    
    if result['updated_files'] > 0:
        print(f"✅ Updated {result['updated_files']} files in index")
    else:
        print("✅ Index is already up to date")

if __name__ == "__main__":
    asyncio.run(main())
```

## Phase 3: MCP Integration (Week 1-2)

### 3.1 Add New MCP Tools

**Update: `src/server.py`**

```python
# Add to initialization
semantic_engine = SemanticSearchEngine()
code_indexer = CodeIndexer()

@app.tool()
async def semantic_search(
    query: str,
    limit: int = 20,
    file_types: Optional[List[str]] = None,
    include_code: bool = False,
    hybrid_mode: bool = True
) -> Dict:
    """
    Search code using natural language queries.
    
    Examples:
    - "functions that submit files to the celery queue"
    - "error handling for database connections"
    - "code that validates user input"
    - "authentication middleware"
    """
    results = await semantic_engine.search(
        query, limit, file_types, hybrid_mode=hybrid_mode
    )
    
    # Format for Claude Code
    return format_semantic_results(results, include_code)

@app.tool()
async def index_codebase(
    paths: Optional[List[str]] = None,
    force_reindex: bool = False
) -> Dict:
    """Index or re-index the codebase for semantic search"""
    paths = paths or ["."]
    result = await code_indexer.index_codebase(paths, force=force_reindex)
    return result

@app.tool()
async def find_similar_code(
    file_path: str,
    line_number: int,
    limit: int = 10
) -> Dict:
    """Find code similar to the given location"""
    # Extract symbol at location
    symbol = await get_symbol_at_location(file_path, line_number)
    if not symbol:
        return {"error": "No symbol found at location"}
    
    # Search for similar code
    context = code_indexer.embedder.create_code_context(symbol)
    embedding = code_indexer.embedder.embed([context])[0]
    
    results = code_indexer.vector_store.search(embedding, limit + 1)
    # Remove self from results
    results = [r for r in results if r["id"] != f"{file_path}:{line_number}:{symbol.name}"]
    
    return {"similar_code": results[:limit]}
```

### 2.2 Query Enhancement

**File: `src/query_enhancer.py`**

```python
class QueryEnhancer:
    def __init__(self):
        self.synonyms = {
            # Task/Queue related
            "submit": ["enqueue", "send", "dispatch", "queue", "schedule", "add"],
            "celery": ["task", "worker", "async", "job", "background"],
            "queue": ["queue", "broker", "task", "job", "worker"],
            
            # File/Data related
            "file": ["document", "data", "content", "object", "blob", "upload"],
            "process": ["handle", "parse", "transform", "analyze", "compute"],
            
            # Error handling
            "error": ["exception", "failure", "catch", "handle", "raise"],
            "retry": ["retry", "attempt", "backoff", "repeat"],
            
            # Authentication
            "auth": ["authenticate", "authorize", "login", "verify", "credential"],
            "user": ["user", "account", "identity", "principal"],
        }
        
        self.code_patterns = {
            "celery_submit": ["delay(", "apply_async(", "@task", "@shared_task"],
            "error_handling": ["try:", "except:", "catch", "finally:", "raise"],
            "authentication": ["authenticate", "login", "@login_required", "jwt"],
        }
    
    def enhance(self, query: str) -> str:
        query_lower = query.lower()
        enhanced_parts = [query]
        
        # Add synonyms
        for word, synonyms in self.synonyms.items():
            if word in query_lower:
                enhanced_parts.extend(synonyms)
        
        # Add code patterns if relevant
        if "celery" in query_lower or "queue" in query_lower:
            enhanced_parts.extend(self.code_patterns["celery_submit"])
        
        if "error" in query_lower or "exception" in query_lower:
            enhanced_parts.extend(self.code_patterns["error_handling"])
        
        return " ".join(enhanced_parts)
```

## Phase 3: CodeBERT Upgrade Path (Week 3-4)

### 3.1 Abstract Embedder Interface

**File: `src/embedders/base.py`**

```python
from abc import ABC, abstractmethod

class BaseEmbedder(ABC):
    @abstractmethod
    def embed_code(self, code: str, language: str) -> np.ndarray:
        """Embed source code"""
        pass
    
    @abstractmethod
    def embed_text(self, text: str) -> np.ndarray:
        """Embed natural language text"""
        pass
    
    @abstractmethod
    def embed_batch(self, items: List[Dict]) -> np.ndarray:
        """Batch embed mixed content"""
        pass
```

### 3.2 Sentence-Transformer Implementation

**File: `src/embedders/sentence_transformer.py`**

```python
class SentenceTransformerEmbedder(BaseEmbedder):
    def __init__(self, model_name="all-mpnet-base-v2"):
        self.model = SentenceTransformer(model_name)
    
    def embed_code(self, code: str, language: str) -> np.ndarray:
        # Add language context
        context = f"Language: {language}\nCode:\n{code}"
        return self.model.encode(context)
    
    def embed_text(self, text: str) -> np.ndarray:
        return self.model.encode(text)
    
    def embed_batch(self, items: List[Dict]) -> np.ndarray:
        texts = []
        for item in items:
            if item["type"] == "code":
                text = f"Language: {item['language']}\nCode:\n{item['content']}"
            else:
                text = item["content"]
            texts.append(text)
        return self.model.encode(texts, batch_size=32)
```

### 3.3 CodeBERT Implementation

**File: `src/embedders/codebert.py`**

```python
class CodeBERTEmbedder(BaseEmbedder):
    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained("microsoft/codebert-base")
        self.model = AutoModel.from_pretrained("microsoft/codebert-base")
        self.model.eval()
    
    def embed_code(self, code: str, language: str) -> np.ndarray:
        # CodeBERT expects code and language
        inputs = self.tokenizer(
            code,
            truncation=True,
            max_length=512,
            padding=True,
            return_tensors="pt"
        )
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            # Use pooler output for sentence embedding
            embedding = outputs.pooler_output.squeeze().numpy()
        
        return embedding
    
    def embed_text(self, text: str) -> np.ndarray:
        # For queries, use natural language
        return self.embed_code(text, "natural")
```

### 3.4 Hybrid Embedder

**File: `src/embedders/hybrid.py`**

```python
class HybridEmbedder(BaseEmbedder):
    def __init__(self, code_weight=0.7, text_weight=0.3):
        self.code_embedder = CodeBERTEmbedder()
        self.text_embedder = SentenceTransformerEmbedder()
        self.code_weight = code_weight
        self.text_weight = text_weight
    
    def embed_code(self, code: str, language: str) -> np.ndarray:
        # Use CodeBERT for code
        code_emb = self.code_embedder.embed_code(code, language)
        
        # Use sentence-transformer for docstring/context
        context = extract_context(code)
        text_emb = self.text_embedder.embed_text(context)
        
        # Weighted combination
        return (self.code_weight * code_emb + 
                self.text_weight * text_emb)
```

### 3.5 Configuration System

**File: `config/semantic_search.yaml`**

```yaml
semantic_search:
  # Embedder configuration
  embedder:
    # Start with sentence-transformers
    type: "sentence-transformer"
    model: "all-mpnet-base-v2"
    
    # Upgrade to CodeBERT
    # type: "codebert"
    # model: "microsoft/codebert-base"
    
    # Or use hybrid
    # type: "hybrid"
    # code_weight: 0.7
    # text_weight: 0.3
  
  # Vector store configuration
  vector_store:
    type: "chromadb"
    persist_directory: "./chroma_db"
    collection_name: "code_search"
  
  # Search configuration
  search:
    default_limit: 20
    similarity_threshold: 0.7
    hybrid_mode: true
    keyword_weight: 0.2
    semantic_weight: 0.8
  
  # Indexing configuration
  indexing:
    batch_size: 32
    max_symbol_size: 10000  # Skip very large symbols
    include_docstrings: true
    include_comments: true
```

## Phase 4: Advanced Features (Week 4+)

### 4.1 Incremental Indexing

```python
class IncrementalIndexer:
    def __init__(self, vector_store, embedder):
        self.vector_store = vector_store
        self.embedder = embedder
        self.file_hashes = self.load_file_hashes()
    
    async def update_changed_files(self, files: List[str]):
        """Update only changed files in the index"""
        changed = []
        for file in files:
            current_hash = calculate_file_hash(file)
            if self.file_hashes.get(file) != current_hash:
                changed.append(file)
                self.file_hashes[file] = current_hash
        
        if changed:
            # Remove old entries
            for file in changed:
                self.vector_store.delete(where={"file": file})
            
            # Add new entries
            await self.index_files(changed)
        
        self.save_file_hashes()
        return {"updated_files": len(changed)}
```

### 4.2 Code Understanding Features

```python
class CodeUnderstanding:
    def extract_function_calls(self, code: str, language: str) -> List[str]:
        """Extract function calls from code"""
        if language == "python":
            # Use AST to find function calls
            tree = ast.parse(code)
            calls = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        calls.append(node.func.id)
                    elif isinstance(node.func, ast.Attribute):
                        calls.append(node.func.attr)
            return calls
        # Add other languages...
    
    def extract_imports(self, code: str, language: str) -> List[str]:
        """Extract imports/includes"""
        if language == "python":
            tree = ast.parse(code)
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(n.name for n in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imports.append(node.module)
            return imports
        # Add other languages...
```

## Testing Strategy

### 1. Benchmark Dataset

Create a benchmark with known queries and expected results:

```python
benchmarks = [
    {
        "query": "functions that submit files to the celery queue",
        "expected_functions": ["submit_to_celery", "enqueue_file_task", "async_file_processor"],
        "should_not_find": ["download_file", "read_config"]
    },
    {
        "query": "error handling for database connections",
        "expected_functions": ["handle_db_error", "retry_connection", "log_db_exception"],
        "should_not_find": ["create_user", "update_record"]
    },
    {
        "query": "user authentication and authorization",
        "expected_functions": ["authenticate_user", "check_permissions", "validate_token"],
        "should_not_find": ["create_database", "send_email"]
    }
]
```

### 2. Evaluation Metrics

```python
class SearchEvaluator:
    def evaluate(self, query: str, results: List[Dict], expected: List[str]) -> Dict:
        found = [r["name"] for r in results]
        
        # Precision: How many results are relevant?
        relevant_found = [f for f in found if f in expected]
        precision = len(relevant_found) / len(found) if found else 0
        
        # Recall: Did we find all expected results?
        recall = len(relevant_found) / len(expected) if expected else 0
        
        # F1 Score
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        # Mean Reciprocal Rank (MRR)
        for i, result in enumerate(found):
            if result in expected:
                mrr = 1 / (i + 1)
                break
        else:
            mrr = 0
        
        return {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "mrr": mrr,
            "found": found[:10],
            "expected": expected
        }
```

### 3. Performance Testing

```python
async def performance_test():
    # Test indexing speed
    start = time.time()
    await indexer.index_codebase(["."])
    index_time = time.time() - start
    
    # Test search speed
    queries = ["celery queue", "error handling", "authentication"]
    search_times = []
    
    for query in queries:
        start = time.time()
        await semantic_engine.search(query)
        search_times.append(time.time() - start)
    
    return {
        "index_time": index_time,
        "avg_search_time": sum(search_times) / len(search_times),
        "symbols_indexed": vector_store.collection.count(),
        "index_size_mb": get_directory_size("./chroma_db") / 1024 / 1024
    }
```

## Workflow and Timing

### Typical Usage Workflow

1. **Initial Setup** (one-time):
   ```bash
   # Install dependencies
   ./scripts/setup_semantic_search.sh
   
   # Build initial index
   python scripts/build_semantic_index.py
   # Expected time for 196 files/54k LOC: ~30-60 seconds
   ```

2. **Daily Development**:
   ```bash
   # Start MCP server (index already exists)
   ./run_server.sh
   # Server starts immediately, semantic search ready
   ```

3. **After Major Changes**:
   ```bash
   # Check if reindex needed
   python scripts/check_index.py
   
   # Update incrementally or rebuild
   python scripts/update_index.py  # Fast, only changed files
   # OR
   python scripts/build_semantic_index.py --force  # Full rebuild
   ```

### Indexing Time Estimates

For your 196 files/54k LOC project:

| Operation | Estimated Time | When to Use |
|-----------|---------------|-------------|
| Initial index | 30-60 seconds | First time setup |
| Full rebuild | 30-60 seconds | Major refactoring |
| Incremental update | 5-10 seconds | Daily changes |
| Index status check | <1 second | Before coding session |
| Semantic search | <100ms | During development |

### Storage Estimates

- **Index size**: ~20-40MB for 54k LOC
- **Metadata**: <1MB
- **Model cache**: ~420MB (downloaded once)
- **Total disk usage**: ~500MB

## Resource Requirements

### Sentence-Transformers
- **Model size**: ~420MB (all-mpnet-base-v2)
- **Memory usage**: ~500MB during indexing, ~300MB runtime
- **Indexing speed**: ~100 symbols/second
- **Search latency**: <100ms for 10k symbols
- **Vector dimensions**: 768

### CodeBERT
- **Model size**: ~440MB
- **Memory usage**: ~1.5GB during indexing, ~1GB runtime
- **Indexing speed**: ~20 symbols/second
- **Search latency**: <200ms for 10k symbols
- **Vector dimensions**: 768

### Storage Requirements
- **ChromaDB**: ~1MB per 1000 symbols
- **File hashes**: ~100KB for 1000 files
- **Total for 54k LOC**: ~50-100MB

## Migration Checklist

- [ ] Implement sentence-transformer embedder
- [ ] Create vector store with ChromaDB
- [ ] Build indexing pipeline
- [ ] Add semantic_search MCP tool
- [ ] Test with benchmark queries
- [ ] Measure performance metrics
- [ ] Document query examples
- [ ] Create CodeBERT embedder
- [ ] Implement embedder switching
- [ ] Compare model performance
- [ ] Choose best configuration
- [ ] Add incremental indexing
- [ ] Implement file watching (optional)

## Success Criteria

1. **Functionality**: Can find "functions that submit to celery queue"
2. **Performance**: <2s indexing for 1000 symbols, <100ms search
3. **Accuracy**: >80% precision on benchmark queries
4. **Integration**: Works seamlessly with existing MCP tools
5. **Upgradeability**: Can switch embedders without re-indexing