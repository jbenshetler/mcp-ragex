#!/usr/bin/env python3
"""Test comment and docstring extraction for semantic search"""

import asyncio
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.tree_sitter_enhancer import TreeSitterEnhancer

@pytest.mark.asyncio
async def test_comment_extraction():
    enhancer = TreeSitterEnhancer()
    
    # Test file with comments
    test_file = "tests/data/test_comments.py"
    
    print("Testing comment extraction for semantic search")
    print("=" * 60)
    
    # Extract with comments (for semantic search)
    print("\n1. WITH comments and docstrings (semantic search):")
    symbols_with_comments = await enhancer.extract_symbols(test_file, include_docs_and_comments=True)
    
    # Group by type
    by_type = {}
    for symbol in symbols_with_comments:
        symbol_type = symbol.type
        if symbol_type not in by_type:
            by_type[symbol_type] = []
        by_type[symbol_type].append(symbol)
    
    for symbol_type, symbols in by_type.items():
        print(f"\n{symbol_type.upper()} ({len(symbols)}):")
        for sym in symbols:
            if symbol_type in ['comment', 'module_doc']:
                print(f"  - {sym.name}")
                if sym.signature and sym.signature != 'comment':
                    print(f"    Type: {sym.signature}")
                print(f"    Line: {sym.line}")
                if symbol_type == 'comment':
                    print(f"    Text: {sym.code[:60]}...")
            else:
                print(f"  - {sym.name}")
    
    print("\n" + "=" * 60)
    
    # Extract without comments (for symbol search)
    print("\n2. WITHOUT comments and docstrings (symbol search):")
    symbols_without_comments = await enhancer.extract_symbols(test_file, include_docs_and_comments=False)
    
    print(f"Found {len(symbols_without_comments)} symbols")
    for sym in symbols_without_comments:
        print(f"  - {sym.type}: {sym.name}")

if __name__ == "__main__":
    asyncio.run(test_comment_extraction())