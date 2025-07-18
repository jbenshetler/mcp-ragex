#!/usr/bin/env python3
"""
MCP Server Launcher - Ensures proper environment and stdio handling

This launcher:
1. Adds the MCP venv site-packages to Python path
2. Preserves stdio for MCP communication
3. Launches the server with proper environment
"""

import os
import sys
import site
from pathlib import Path

# Get the directory where this launcher is located
LAUNCHER_DIR = Path(__file__).parent.absolute()
MCP_VENV_DIR = LAUNCHER_DIR / ".mcp_venv"

# Add MCP venv site-packages to Python path
if MCP_VENV_DIR.exists():
    # Find the site-packages directory in the MCP venv
    python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    site_packages = MCP_VENV_DIR / "lib" / python_version / "site-packages"
    
    if site_packages.exists():
        # Add to beginning of path to take precedence
        sys.path.insert(0, str(site_packages))
        # Also add the venv's site-packages using site.addsitedir for .pth files
        site.addsitedir(str(site_packages))
    else:
        # Try alternative location (some systems use lib64)
        site_packages = MCP_VENV_DIR / "lib64" / python_version / "site-packages"
        if site_packages.exists():
            sys.path.insert(0, str(site_packages))
            site.addsitedir(str(site_packages))

# Now import and run the server
sys.path.insert(0, str(LAUNCHER_DIR / "src"))

# Import the server module
from server import main
import asyncio

if __name__ == "__main__":
    # Run the server - this preserves stdio communication
    asyncio.run(main())