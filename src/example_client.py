#!/usr/bin/env python3
"""
Example client showing how to use the MCP code search server
"""

import asyncio
import json
from pathlib import Path

# This is a simplified example - in production, use the official MCP client SDK
async def example_usage():
    """Show example search queries"""
    
    print("MCP Code Search Server - Example Usage")
    print("=" * 50)
    print()
    
    # Example 1: Search for function definitions
    print("1. Search for Python async functions:")
    print('   Tool: search_code')
    print('   Arguments: {"pattern": "async def", "file_types": ["py"], "limit": 10}')
    print()
    
    # Example 2: Search for TODO comments
    print("2. Search for TODO comments in all files:")
    print('   Tool: search_code')
    print('   Arguments: {"pattern": "TODO|FIXME", "case_sensitive": false}')
    print()
    
    # Example 3: Search for class definitions
    print("3. Search for class definitions across multiple languages:")
    print('   Tool: search_code')
    print('   Arguments: {"pattern": "class\\s+\\w+", "file_types": ["py", "js", "ts", "java"]}')
    print()
    
    # Example 4: Search for imports
    print("4. Search for specific imports:")
    print('   Tool: search_code')
    print('   Arguments: {"pattern": "import.*pandas|from pandas", "file_types": ["py"]}')
    print()
    
    # Example 5: Search in specific directories
    print("5. Search in specific directories:")
    print('   Tool: search_code')
    print('   Arguments: {"pattern": "test_", "paths": ["tests", "test"], "file_types": ["py"]}')
    print()
    
    # Example 6: Search with symbol context (Tree-sitter enhancement)
    print("6. Search with symbol context (shows containing function/class):")
    print('   Tool: search_code')
    print('   Arguments: {"pattern": "TODO", "include_symbols": true, "limit": 10}')
    print()
    
    # Example 7: Search with custom exclusions
    print("7. Search with custom file exclusions:")
    print('   Tool: search_code')
    print('   Arguments: {"pattern": "import", "exclude_patterns": ["tests/**", "*.spec.js"], "file_types": ["js", "ts"]}')
    print()
    
    # Example 8: Raw format for programmatic use
    print("8. Get results in raw format (just file:line):")
    print('   Tool: search_code')
    print('   Arguments: {"pattern": "TODO", "format": "raw", "limit": 20}')
    print()
    
    # Integration example
    print("\nIntegration with Claude Desktop (claude_desktop_config.json):")
    print(json.dumps({
        "mcpServers": {
            "coderag": {
                "command": "python",
                "args": [str(Path(__file__).parent / "server.py")],
                "env": {}
            }
        }
    }, indent=2))
    
    print("\n\nCommon patterns for coding assistants:")
    print("""
    - "Where is X defined?" -> search_code with pattern "def X|function X|class X"
    - "Find all tests" -> search_code with pattern "test_|describe\\(|it\\(" 
    - "Show error handling" -> search_code with pattern "try|catch|except|raise|throw"
    - "Find API endpoints" -> search_code with pattern "@app.route|@router|@Get|@Post"
    - "Find database queries" -> search_code with pattern "SELECT|INSERT|UPDATE|DELETE|query\\("
    """)


if __name__ == "__main__":
    asyncio.run(example_usage())