#!/usr/bin/env python3
"""
MCP Server Entry Point

This script ensures proper environment setup and stdio handling for MCP communication.
It should be run by the MCP venv Python interpreter.
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    # Ensure unbuffered output
    os.environ['PYTHONUNBUFFERED'] = '1'
    
    # Get the directory where this entry point is located
    entry_dir = Path(__file__).parent.absolute()
    
    # Add src to Python path
    sys.path.insert(0, str(entry_dir / "src"))
    
    # Import and run the server directly in this process
    # This avoids any subprocess issues with stdio
    from server import main as server_main
    import asyncio
    
    # Run the server
    asyncio.run(server_main())

if __name__ == "__main__":
    main()