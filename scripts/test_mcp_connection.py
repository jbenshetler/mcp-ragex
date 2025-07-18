#!/usr/bin/env python3
"""
Test MCP Server Connection

This script tests that the MCP server can be started and communicated with properly.
"""

import subprocess
import json
import os
import sys
from pathlib import Path

def test_wrapper_script(script_path):
    """Test if the wrapper script allows proper stdio communication"""
    print(f"\nTesting wrapper script: {script_path}")
    
    # Set up environment
    env = os.environ.copy()
    env['MCP_WORKING_DIR'] = os.getcwd()
    
    # Test basic execution
    try:
        # Send a simple JSON-RPC request to list tools
        test_request = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 1
        }
        
        # Start the process
        proc = subprocess.Popen(
            [str(script_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            bufsize=0  # Unbuffered
        )
        
        # Send initialization
        init_request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "capabilities": {}
            },
            "id": 0
        }
        
        print("Sending initialization request...")
        proc.stdin.write(json.dumps(init_request) + '\n')
        proc.stdin.flush()
        
        # Try to read response
        print("Waiting for response...")
        response_line = proc.stdout.readline()
        if response_line:
            print(f"Got response: {response_line.strip()}")
            response = json.loads(response_line)
            print(f"Parsed response: {json.dumps(response, indent=2)}")
        else:
            print("No response received")
            
        # Check stderr
        stderr = proc.stderr.read()
        if stderr:
            print(f"Stderr output: {stderr}")
            
        proc.terminate()
        proc.wait()
        
    except Exception as e:
        print(f"Error testing wrapper: {e}")
        import traceback
        traceback.print_exc()

def test_python_availability():
    """Test if the MCP venv Python has required packages"""
    print("\nTesting MCP venv Python environment...")
    
    script_dir = Path(__file__).parent.parent
    mcp_python = script_dir / ".mcp_venv" / "bin" / "python"
    
    if not mcp_python.exists():
        print(f"MCP Python not found at: {mcp_python}")
        return
        
    # Test imports
    test_code = """
import sys
print(f"Python: {sys.executable}")
print(f"Version: {sys.version}")

try:
    import numpy
    print("✓ numpy available")
except ImportError as e:
    print(f"✗ numpy not available: {e}")

try:
    import sentence_transformers
    print("✓ sentence_transformers available")
except ImportError as e:
    print(f"✗ sentence_transformers not available: {e}")

try:
    import chromadb
    print("✓ chromadb available")
except ImportError as e:
    print(f"✗ chromadb not available: {e}")

try:
    import mcp
    print("✓ mcp available")
except ImportError as e:
    print(f"✗ mcp not available: {e}")
"""
    
    result = subprocess.run(
        [str(mcp_python), "-c", test_code],
        capture_output=True,
        text=True
    )
    
    print("Output:")
    print(result.stdout)
    if result.stderr:
        print("Errors:")
        print(result.stderr)

def main():
    print("MCP Server Connection Diagnostic")
    print("=" * 50)
    
    # Test Python environment
    test_python_availability()
    
    # Test wrapper scripts
    script_dir = Path(__file__).parent.parent
    
    # Test the isolated wrapper
    isolated_wrapper = script_dir / "mcp_server_isolated.sh"
    if isolated_wrapper.exists():
        test_wrapper_script(isolated_wrapper)
    else:
        print(f"Isolated wrapper not found: {isolated_wrapper}")
    
    # Test the original wrapper
    original_wrapper = script_dir / "mcp_coderag_pwd.sh"
    if original_wrapper.exists():
        test_wrapper_script(original_wrapper)

if __name__ == "__main__":
    main()