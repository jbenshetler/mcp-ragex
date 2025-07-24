#!/usr/bin/env python3
"""
Test script for the MCP code search server
"""

import asyncio
import json
import subprocess
from pathlib import Path
import pytest


@pytest.mark.asyncio
async def test_direct_search():
    """Test the searcher directly without MCP protocol"""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    
    from server import RipgrepSearcher
    
    searcher = RipgrepSearcher()
    
    print("Testing direct search functionality...")
    
    # Test 1: Basic search
    result = await searcher.search("def", file_types=["py"], limit=5)
    print(f"\nTest 1 - Basic search for 'def':")
    print(f"Success: {result['success']}")
    print(f"Matches found: {result.get('total_matches', 0)}")
    
    # Test 2: Case insensitive search
    result = await searcher.search("TODO", case_sensitive=False, limit=10)
    print(f"\nTest 2 - Case insensitive search for 'TODO':")
    print(f"Success: {result['success']}")
    print(f"Matches found: {result.get('total_matches', 0)}")
    
    # Test 3: Invalid regex
    result = await searcher.search("[invalid(", limit=5)
    print(f"\nTest 3 - Invalid regex pattern:")
    print(f"Success: {result['success']}")
    if not result['success']:
        print(f"Error: {result.get('error', 'None')}")
    else:
        print("Error: Test should have failed!")
    
    # Test 4: Multiple file types
    result = await searcher.search("import", file_types=["py", "js", "ts"], limit=10)
    print(f"\nTest 4 - Search across multiple file types:")
    print(f"Success: {result['success']}")
    print(f"Matches found: {result.get('total_matches', 0)}")


def test_mcp_protocol():
    """Test the server using MCP protocol via stdin/stdout"""
    print("\n\nTesting MCP protocol...")
    
    # Start the server process
    server_path = Path(__file__).parent.parent / "src" / "server.py"
    proc = subprocess.Popen(
        ["python", str(server_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    
    try:
        # Send initialize request
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "0.1.0",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "0.1.0"
                }
            }
        }
        
        proc.stdin.write(json.dumps(init_request) + "\n")
        proc.stdin.flush()
        
        # Read response
        response = proc.stdout.readline()
        print(f"\nInitialize response: {response[:100]}...")
        
        # Send list tools request
        list_tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        proc.stdin.write(json.dumps(list_tools_request) + "\n")
        proc.stdin.flush()
        
        response = proc.stdout.readline()
        print(f"\nTools list response: {response[:200]}...")
        
        # Send search request
        search_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "search_code",
                "arguments": {
                    "pattern": "async def",
                    "file_types": ["py"],
                    "limit": 5
                }
            }
        }
        
        proc.stdin.write(json.dumps(search_request) + "\n")
        proc.stdin.flush()
        
        response = proc.stdout.readline()
        print(f"\nSearch response: {response[:300]}...")
        
    finally:
        proc.terminate()
        proc.wait()


def create_test_files():
    """Create some test files to search through"""
    test_dir = Path("test_files")
    test_dir.mkdir(exist_ok=True)
    
    # Python file
    (test_dir / "example.py").write_text("""
def hello_world():
    print("Hello, World!")

async def fetch_data():
    # TODO: Implement data fetching
    pass

class UserService:
    def __init__(self):
        self.users = []
    
    def add_user(self, user):
        self.users.append(user)
""")
    
    # JavaScript file
    (test_dir / "example.js").write_text("""
function greet(name) {
    console.log(`Hello, ${name}!`);
}

const fetchData = async () => {
    // TODO: Add API call
    return [];
};

class UserService {
    constructor() {
        this.users = [];
    }
}
""")
    
    # TypeScript file
    (test_dir / "example.ts").write_text("""
interface User {
    id: number;
    name: string;
}

async function fetchUsers(): Promise<User[]> {
    // TODO: Implement API call
    return [];
}

class UserService {
    private users: User[] = [];
    
    addUser(user: User): void {
        this.users.push(user);
    }
}
""")
    
    print("Test files created in test_files/")


if __name__ == "__main__":
    print("MCP Code Search Server Test Suite")
    print("=" * 50)
    
    # Create test files
    create_test_files()
    
    # Run tests
    asyncio.run(test_direct_search())
    
    # Test MCP protocol (commented out by default as it requires proper MCP client)
    # test_mcp_protocol()
    
    print("\n\nTests completed!")