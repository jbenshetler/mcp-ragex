#!/usr/bin/env python3
"""
Test Tree-sitter integration and performance
"""

import asyncio
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tree_sitter_enhancer import TreeSitterEnhancer
from server import RipgrepSearcher


async def test_symbol_extraction():
    """Test basic symbol extraction"""
    print("Testing Tree-sitter symbol extraction...")
    
    enhancer = TreeSitterEnhancer()
    
    # Test on our own source files
    test_files = [
        "src/server.py",
        "src/tree_sitter_enhancer.py",
        "src/example_client.py",
    ]
    
    for file_path in test_files:
        if Path(file_path).exists():
            print(f"\nExtracting symbols from {file_path}:")
            symbols = await enhancer.extract_symbols(file_path)
            print(f"  Found {len(symbols)} symbols")
            
            # Show first few symbols
            for symbol in symbols[:5]:
                print(f"  - {symbol.type} '{symbol.name}' at line {symbol.line}")
                if symbol.parent:
                    print(f"    Parent: {symbol.parent}")
                if symbol.signature:
                    print(f"    Signature: {symbol.signature}")


async def test_search_enhancement():
    """Test search result enhancement"""
    print("\n\nTesting search result enhancement...")
    
    searcher = RipgrepSearcher()
    enhancer = TreeSitterEnhancer()
    
    # Search for async functions
    print("\nSearching for 'async def' with symbol context:")
    
    # First, regular search
    start_time = time.time()
    result = await searcher.search("async def", file_types=["py"], limit=10)
    regular_time = time.time() - start_time
    
    print(f"Regular search took {regular_time:.3f}s")
    print(f"Found {result['total_matches']} matches")
    
    # Now with enhancement
    start_time = time.time()
    enhanced_result = await enhancer.enhance_search_results(result)
    enhance_time = time.time() - start_time
    
    print(f"Enhancement took {enhance_time:.3f}s")
    
    # Show enhanced results
    if enhanced_result.get("matches"):
        print("\nEnhanced results:")
        for match in enhanced_result["matches"][:5]:
            print(f"\n{match['file']}:{match['line_number']}")
            print(f"  Line: {match['line'].strip()}")
            if "symbol_context" in match:
                ctx = match["symbol_context"]
                print(f"  Context: {ctx['type']} '{ctx['name']}'")
                if ctx.get('signature'):
                    print(f"  Signature: {ctx['signature']}")


async def test_performance_at_scale():
    """Test performance with multiple files"""
    print("\n\nTesting performance at scale...")
    
    enhancer = TreeSitterEnhancer()
    
    # Find all Python, JS, and TS files in the project
    file_types = {".py", ".js", ".jsx", ".ts", ".tsx"}
    all_files = []
    
    for pattern in ["**/*.py", "**/*.js", "**/*.jsx", "**/*.ts", "**/*.tsx"]:
        all_files.extend(Path(".").glob(pattern))
    
    # Filter out node_modules and similar
    filtered_files = [
        f for f in all_files 
        if "node_modules" not in str(f) 
        and ".venv" not in str(f)
        and "__pycache__" not in str(f)
    ]
    
    print(f"Found {len(filtered_files)} files to process")
    
    # Test symbol extraction performance
    start_time = time.time()
    total_symbols = 0
    
    # Process first 20 files as a sample
    sample_size = min(20, len(filtered_files))
    for file_path in filtered_files[:sample_size]:
        try:
            symbols = await enhancer.extract_symbols(str(file_path))
            total_symbols += len(symbols)
        except Exception as e:
            print(f"  Error processing {file_path}: {e}")
    
    elapsed_time = time.time() - start_time
    
    print(f"\nProcessed {sample_size} files in {elapsed_time:.2f}s")
    print(f"Average time per file: {elapsed_time/sample_size:.3f}s")
    print(f"Total symbols extracted: {total_symbols}")
    
    # Estimate for 196 files
    if sample_size > 0:
        estimated_time = (elapsed_time / sample_size) * 196
        print(f"\nEstimated time for 196 files: {estimated_time:.1f}s")
        print(f"Estimated time for 54k LOC (assuming ~275 LOC/file): {estimated_time:.1f}s")


async def test_memory_usage():
    """Test memory usage with caching"""
    print("\n\nTesting memory usage...")
    
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    
    enhancer = TreeSitterEnhancer()
    
    # Initial memory
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB
    print(f"Initial memory usage: {initial_memory:.1f} MB")
    
    # Process multiple files
    test_files = ["src/server.py", "src/tree_sitter_enhancer.py"] * 10
    
    for i, file_path in enumerate(test_files):
        await enhancer.extract_symbols(file_path)
        
        if i % 5 == 0:
            current_memory = process.memory_info().rss / 1024 / 1024
            print(f"After {i+1} files: {current_memory:.1f} MB (Δ {current_memory-initial_memory:.1f} MB)")
    
    # Check cache size
    print(f"\nCache contains {len(enhancer._symbol_cache)} files")
    print(f"File read cache size: {len(enhancer._read_file_cached.cache_info())}")


if __name__ == "__main__":
    print("Tree-sitter Integration Test Suite")
    print("=" * 50)
    
    asyncio.run(test_symbol_extraction())
    asyncio.run(test_search_enhancement())
    asyncio.run(test_performance_at_scale())
    
    # Only run memory test if psutil is available
    try:
        import psutil
        asyncio.run(test_memory_usage())
    except ImportError:
        print("\nSkipping memory test (psutil not installed)")
    
    print("\n\nTests completed!")