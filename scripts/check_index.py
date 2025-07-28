#!/usr/bin/env python3
"""
Check semantic search index status.
Shows index information, age, and whether it needs rebuilding.

Usage:
    uv run check_index.py
"""
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "chromadb>=0.4.0",
#     "pathspec>=0.11.0",
# ]
# ///

import json
from pathlib import Path
from datetime import datetime
import sys

# Add parent directory to path to find ragexmcp modules
script_dir = Path(__file__).parent
ragexmcp_dir = script_dir.parent

# Change to the ragexmcp directory so relative imports work
import os
original_cwd = os.getcwd()
os.chdir(str(ragexmcp_dir))

# Add both the ragexmcp directory and src to path
sys.path.insert(0, str(ragexmcp_dir))
sys.path.insert(0, str(ragexmcp_dir / "src"))

try:
    from src.vector_store import CodeVectorStore
    from src.pattern_matcher import PatternMatcher
except ImportError as e:
    print(f"❌ Cannot import required modules from ragexmcp directory.")
    print(f"   Script location: {script_dir}")
    print(f"   RAGex directory: {ragexmcp_dir}")
    print(f"   Error: {e}")
    print(f"   Make sure the ragexmcp directory contains src/vector_store.py and src/pattern_matcher.py")
    os.chdir(original_cwd)
    sys.exit(1)


def main():
    # Check for index in the original working directory
    index_path = Path(original_cwd) / "chroma_db"
    
    if not index_path.exists():
        print("❌ No semantic search index found.")
        print("   Run: uv run build_semantic_index.py . --stats")
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
        print(f"🤖 Model: {metadata.get('model', 'unknown')}")
        
        # Check for changes
        pattern_matcher = PatternMatcher()
        changed_files = []
        
        for path in metadata['paths']:
            for ext in [".py", ".js", ".jsx", ".ts", ".tsx"]:
                for file in Path(path).rglob(f"*{ext}"):
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
            print("\n💡 Consider rebuilding: uv run build_semantic_index.py . --force --stats")
        else:
            print("\n✅ Index is up to date")
            
        # Show vector store statistics
        try:
            vector_store = CodeVectorStore(persist_directory=str(index_path))
            stats = vector_store.get_statistics()
            print(f"\n📈 Vector Store Statistics:")
            print(f"   - Total symbols: {stats['total_symbols']}")
            print(f"   - Index size: {stats.get('index_size_mb', 0):.1f} MB")
            print(f"   - Unique files: {stats['unique_files']}")
            
            if stats.get('types'):
                print(f"   - Symbol types: {dict(list(stats['types'].items())[:5])}")
            if stats.get('languages'):
                print(f"   - Languages: {dict(stats['languages'].items())}")
                
        except Exception as e:
            print(f"\n⚠️  Could not load vector store statistics: {e}")
            
    else:
        print("⚠️  Index exists but metadata is missing")
        print("   Consider rebuilding: uv run build_semantic_index.py . --force --stats")


if __name__ == "__main__":
    try:
        main()
    finally:
        # Restore original working directory
        os.chdir(original_cwd)