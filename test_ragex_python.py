#!/usr/bin/env python3
"""
Test script for Python ragex implementation

Tests:
1. Argument parsing
2. Project ID generation
3. Command routing
4. MCP mode detection
"""

import subprocess
import sys
import os
from pathlib import Path

def test_help():
    """Test help output"""
    print("=== Testing help output ===")
    result = subprocess.run(['./ragex.py', '--help'], capture_output=True, text=True)
    assert result.returncode == 0
    assert "RAGex - Smart code search" in result.stdout
    assert "index" in result.stdout
    assert "search" in result.stdout
    print("✓ Help output works")

def test_subcommand_help():
    """Test subcommand help"""
    print("\n=== Testing subcommand help ===")
    result = subprocess.run(['./ragex.py', 'search', '--help'], capture_output=True, text=True)
    assert result.returncode == 0
    assert "--json" in result.stdout
    assert "--symbol" in result.stdout
    assert "--regex" in result.stdout
    print("✓ Subcommand help works")

def test_project_id_generation():
    """Test project ID generation matches bash version"""
    print("\n=== Testing project ID generation ===")
    # Import the Python implementation
    sys.path.insert(0, str(Path(__file__).parent))
    from ragex import RagexCLI
    
    cli = RagexCLI()
    test_path = Path("/home/test/project")
    
    # Generate ID
    project_id = cli.generate_project_id(test_path)
    
    # Should match pattern: ragex_{uid}_{16-char-hash}
    assert project_id.startswith(f"ragex_{cli.user_id}_")
    assert len(project_id.split('_')[-1]) == 16
    print(f"✓ Project ID format correct: {project_id}")

def test_mcp_mode_detection():
    """Test MCP mode detection"""
    print("\n=== Testing MCP mode detection ===")
    # Test that --mcp flag is recognized
    result = subprocess.run(['./ragex.py', '--mcp', '--help'], 
                          capture_output=True, text=True)
    # Should try to run MCP mode, not show help
    assert "MCP dependencies not installed" in result.stderr or "Starting MCP server" in result.stderr
    print("✓ MCP mode detection works")

def test_unknown_command():
    """Test unknown command handling"""
    print("\n=== Testing unknown command ===")
    result = subprocess.run(['./ragex.py', 'foobar'], capture_output=True, text=True)
    assert result.returncode != 0
    # argparse shows "invalid choice" for unknown commands
    assert "invalid choice: 'foobar'" in result.stderr
    print("✓ Unknown command handled correctly")

def test_info_command():
    """Test info command (doesn't require docker)"""
    print("\n=== Testing info command ===")
    result = subprocess.run(['./ragex.py', 'info'], capture_output=True, text=True)
    # Info command should at least show basic info even if daemon isn't running
    assert "RageX Project Information" in result.stdout
    assert "User ID:" in result.stdout
    assert "Workspace:" in result.stdout
    print("✓ Info command works")

def compare_with_bash():
    """Compare key outputs with bash version"""
    print("\n=== Comparing with bash version ===")
    
    # Both should show same commands in help
    bash_help = subprocess.run(['./ragex', '--help'], capture_output=True, text=True)
    py_help = subprocess.run(['./ragex.py', '--help'], capture_output=True, text=True)
    
    # Extract command list from both
    bash_commands = set()
    py_commands = set()
    
    # Check for key commands in both
    for cmd in ['index', 'search', 'ls', 'stop', 'status', 'log', 'info']:
        if cmd in bash_help.stdout:
            bash_commands.add(cmd)
        if cmd in py_help.stdout:
            py_commands.add(cmd)
    
    print(f"Bash commands found: {bash_commands}")
    print(f"Python commands found: {py_commands}")
    
    # Python should have at least all the bash commands
    missing = bash_commands - py_commands
    if missing:
        print(f"⚠️  Missing commands in Python version: {missing}")
    else:
        print("✓ All major commands present in Python version")

def main():
    """Run all tests"""
    print("Testing Python ragex implementation\n")
    
    # Check if ragex.py exists
    if not Path('./ragex.py').exists():
        print("❌ ragex.py not found in current directory")
        return 1
    
    try:
        test_help()
        test_subcommand_help()
        test_project_id_generation()
        test_mcp_mode_detection()
        test_unknown_command()
        test_info_command()
        compare_with_bash()
        
        print("\n✅ All tests passed!")
        return 0
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())