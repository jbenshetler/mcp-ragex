#!/usr/bin/env python3
"""
Diagnose semantic search issues by showing what's in the index
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from embedding_config import EmbeddingConfig
from vector_store import CodeVectorStore
from embedding_manager import EmbeddingManager

def main():
    # Get the ChromaDB path from the project directory
    project_dir = Path.cwd()
    chroma_path = project_dir / "chroma_db"
    
    print(f"Checking ChromaDB at: {chroma_path}")
    
    if not chroma_path.exists():
        print("ERROR: No ChromaDB index found in current directory")
        print("Run: uv run python scripts/build_semantic_index.py . --stats")
        return
    
    # Load the vector store
    config = EmbeddingConfig()
    vector_store = CodeVectorStore(
        persist_directory=str(chroma_path),
        config=config
    )
    
    # Get statistics
    stats = vector_store.get_statistics()
    print(f"\nIndex Statistics:")
    print(f"  Total symbols: {stats['total_symbols']}")
    print(f"  Symbol types: {stats['types']}")
    print(f"  Languages: {stats['languages']}")
    print(f"  Files: {stats['unique_files']}")
    
    # Test some queries
    print("\nTesting semantic search...")
    embedder = EmbeddingManager(config=config)
    
    test_queries = [
        "deduplication functions",
        "duplicate",
        "dedup",
        "TaskDeduplication",
        "acquire_task_lock",
        "release_task_lock"
    ]
    
    for query in test_queries:
        print(f"\nQuery: '{query}'")
        query_embedding = embedder.embed_text(query)
        results = vector_store.search(
            query_embedding=query_embedding,
            limit=5
        )
        
        print(f"  Found {len(results['results'])} matches")
        for i, result in enumerate(results['results'][:3]):
            print(f"  {i+1}. {result['metadata']['file']}:{result['metadata']['line']} "
                  f"[{result['metadata']['type']}] {result['metadata']['name']} "
                  f"(similarity: {1.0 - result['distance']:.3f})")

if __name__ == "__main__":
    main()