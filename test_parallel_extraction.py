#!/usr/bin/env python3
"""
Test script for parallel symbol extraction
"""

import asyncio
import logging
import time
from pathlib import Path
import sys

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test-parallel")

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.parallel_symbol_extractor import ParallelSymbolExtractor
from src.tree_sitter_enhancer import TreeSitterEnhancer
from src.parallel_config import get_optimal_config

async def test_parallel_extraction():
    """Test parallel vs sequential symbol extraction"""
    
    # Find Python files in the current project
    test_files = []
    for py_file in Path("src").rglob("*.py"):
        test_files.append(str(py_file))
    
    if len(test_files) < 2:
        logger.error("Need at least 2 Python files for testing")
        return
    
    # Limit to first 10 files for testing
    test_files = test_files[:10]
    logger.info(f"Testing with {len(test_files)} files: {[Path(f).name for f in test_files]}")
    
    # Test sequential extraction
    logger.info("Testing sequential extraction...")
    sequential_extractor = TreeSitterEnhancer()
    
    start_time = time.time()
    sequential_results = []
    for file_path in test_files:
        symbols = await sequential_extractor.extract_symbols(file_path, include_docs_and_comments=True)
        sequential_results.extend(symbols)
    sequential_time = time.time() - start_time
    
    logger.info(f"Sequential: {len(sequential_results)} symbols in {sequential_time:.2f}s")
    
    # Test parallel extraction
    logger.info("Testing parallel extraction...")
    config = get_optimal_config(len(test_files))
    parallel_extractor = ParallelSymbolExtractor(config=config)
    
    start_time = time.time()
    results = await parallel_extractor.extract_symbols_parallel(
        test_files, 
        include_docs_and_comments=True
    )
    parallel_time = time.time() - start_time
    
    # Count successful results
    parallel_symbols = []
    successful_files = 0
    for result in results:
        if result.success:
            parallel_symbols.extend(result.symbols)
            successful_files += 1
        else:
            logger.warning(f"Failed to extract from {result.file_path}: {result.error}")
    
    logger.info(f"Parallel: {len(parallel_symbols)} symbols in {parallel_time:.2f}s ({successful_files}/{len(test_files)} files)")
    
    # Compare results
    speedup = sequential_time / parallel_time if parallel_time > 0 else 0
    symbol_diff = abs(len(sequential_results) - len(parallel_symbols))
    
    print("\n" + "="*50)
    print("PERFORMANCE COMPARISON")
    print("="*50)
    print(f"Sequential time: {sequential_time:.2f}s")
    print(f"Parallel time:   {parallel_time:.2f}s")
    print(f"Speedup:         {speedup:.2f}x")
    print(f"Workers used:    {config.max_workers}")
    print(f"Sequential symbols: {len(sequential_results)}")
    print(f"Parallel symbols:   {len(parallel_symbols)}")
    print(f"Symbol difference:  {symbol_diff}")
    
    if speedup > 1.0:
        print(f"✅ Parallel extraction is {speedup:.1f}x faster!")
    elif speedup > 0.8:
        print(f"⚠️  Parallel extraction is slightly slower ({speedup:.2f}x)")
    else:
        print(f"❌ Parallel extraction is much slower ({speedup:.2f}x)")
    
    if symbol_diff == 0:
        print("✅ Symbol counts match perfectly")
    elif symbol_diff < 5:
        print(f"⚠️  Small symbol count difference: {symbol_diff}")
    else:
        print(f"❌ Large symbol count difference: {symbol_diff}")

async def test_parallel_config():
    """Test parallel configuration auto-detection"""
    logger.info("Testing parallel configuration...")
    
    config = get_optimal_config()
    print("\n" + "="*50)
    print("PARALLEL CONFIGURATION")
    print("="*50)
    print(f"Max workers:         {config.max_workers}")
    print(f"Min batch size:      {config.min_batch_size}")
    print(f"Max batch size:      {config.max_batch_size}")
    print(f"Target batch time:   {config.target_batch_time}s")
    print(f"Memory limit:        {config.memory_limit_mb}MB")
    print(f"Worker memory limit: {config.worker_memory_limit_mb}MB")
    print(f"Shared parsers:      {config.enable_shared_parsers}")

async def main():
    """Run all tests"""
    try:
        await test_parallel_config()
        await test_parallel_extraction()
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())