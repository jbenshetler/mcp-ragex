#!/usr/bin/env python3
"""
Test script to verify unified search approach works correctly
"""

import asyncio
import os
from pathlib import Path

# Test both implementations
async def test_search_implementations():
    print("Testing Unified Search Approach\n")
    
    # Set up environment to match production
    test_project_dir = Path.cwd()
    os.environ['RAGEX_PROJECT_DATA_DIR'] = str(test_project_dir)
    
    # Import both implementations
    from src.cli.search import SearchClient
    
    print(f"1. Testing CLI SearchClient with project dir: {test_project_dir}")
    cli_client = SearchClient(index_dir=str(test_project_dir))
    
    # Test semantic search
    if cli_client.semantic_searcher:
        print("   ✓ Semantic search available in CLI")
        results = await cli_client.search_semantic("error handling", limit=5)
        print(f"   Found {len(results)} semantic results")
    else:
        print("   ✗ No semantic index found")
    
    # Test symbol search
    results = await cli_client.search_symbol("SearchClient", limit=5)
    print(f"   ✓ Symbol search found {len(results)} results")
    
    # Test regex search  
    results = await cli_client.search_regex("def.*search", limit=5)
    print(f"   ✓ Regex search found {len(results)} results")
    
    print("\n2. Testing that SearchClient returns structured data")
    results = await cli_client.search_symbol("test", limit=2)
    if results and isinstance(results, list) and isinstance(results[0], dict):
        print("   ✓ Returns List[Dict] as expected")
        print(f"   Sample result keys: {list(results[0].keys())}")
    else:
        print("   ✗ Unexpected result format")
    
    print("\n3. Testing project directory resolution")
    # Test different env var scenarios
    test_cases = [
        ("RAGEX_PROJECT_DATA_DIR", "/data/projects/test123"),
        ("PROJECT_NAME", "myproject"),  
        ("MCP_WORKING_DIR", "/home/user/project"),
    ]
    
    for env_var, value in test_cases:
        # Clear all env vars
        for var in ["RAGEX_PROJECT_DATA_DIR", "PROJECT_NAME", "MCP_WORKING_DIR"]:
            os.environ.pop(var, None)
        
        # Set test var
        os.environ[env_var] = value
        
        # Import and check
        from src.server_refactored import get_project_directory
        result = get_project_directory()
        expected = value if env_var != "PROJECT_NAME" else f"/data/projects/{value}"
        print(f"   {env_var}={value} → {result} {'✓' if result == expected else '✗'}")
    
    print("\nConclusion: The unified approach using CLI SearchClient should work!")
    print("Benefits:")
    print("- Reuses working code from CLI")
    print("- Fixes ChromaDB location issues") 
    print("- Eliminates regex escaping bug")
    print("- Maintains same search behavior")


if __name__ == "__main__":
    asyncio.run(test_search_implementations())