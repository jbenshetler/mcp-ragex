#!/usr/bin/env python3
"""Test the enhanced tree-sitter symbol extraction"""

import asyncio
import pytest

import json
from src.tree_sitter_enhancer import TreeSitterEnhancer

@pytest.mark.asyncio
async def test_enhanced_extraction():
    enhancer = TreeSitterEnhancer()
    
    # Test with our sample file
    test_file = "tests/data/test_enhanced_extraction.py"
    symbols = await enhancer.extract_symbols(test_file)
    
    print(f"Found {len(symbols)} symbols in {test_file}\n")
    
    # Group symbols by type
    symbols_by_type = {}
    for symbol in symbols:
        symbol_type = symbol.type
        if symbol_type not in symbols_by_type:
            symbols_by_type[symbol_type] = []
        symbols_by_type[symbol_type].append(symbol)
    
    # Display results
    for symbol_type, type_symbols in symbols_by_type.items():
        print(f"\n{symbol_type.upper()} ({len(type_symbols)}):")
        print("-" * 50)
        for sym in type_symbols:
            print(f"  {sym.name}")
            if sym.signature:
                print(f"    Signature: {sym.signature}")
            if sym.type == "env_var":
                print(f"    Line: {sym.line}")
            print()

if __name__ == "__main__":
    asyncio.run(test_enhanced_extraction())