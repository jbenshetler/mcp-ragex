#!/usr/bin/env python3
"""Handler for register command"""

import logging
import os
import shlex
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


class RegisterHandler:
    """Handles register commands with --help support"""
    
    def __init__(self, shared_modules: Dict[str, Any]):
        self.shared_modules = shared_modules
        self.workspace_path = os.environ.get('WORKSPACE_PATH', '/workspace')
        
    async def handle(self, args: list) -> Dict[str, Any]:
        """Handle register command"""
        try:
            if not args:
                return {
                    'success': False,
                    'stdout': '',
                    'stderr': 'Error: Registration target required (e.g., claude)\n',
                    'returncode': 1
                }
            
            target = args[0]
            
            # Check for --help flag
            if '--help' in args:
                return self._show_help(target)
            
            # Check for --global flag
            is_global = '--global' in args
            
            if target == 'claude':
                return self._register_claude(is_global)
            else:
                return {
                    'success': False,
                    'stdout': '',
                    'stderr': f'Error: Unknown registration target: {target}\n',
                    'returncode': 1
                }
                
        except Exception as e:
            logger.error(f"Register error: {e}", exc_info=True)
            return {
                'success': False,
                'stdout': '',
                'stderr': f"Error: {str(e)}\n",
                'returncode': 1
            }
    
    def _show_help(self, target: str) -> Dict[str, Any]:
        """Show detailed help for register command"""
        if target == 'claude':
            help_text = """Usage: ragex register claude [--global] [--help]

Outputs a shell command to register ragex with Claude.
The output is designed to be piped to sh or used with eval:

  ragex register claude | sh          # Project-scoped
  ragex register claude --global | sh # Global

Options:
  --global    Register globally (all projects) instead of project-scoped

By default, registers for the current project only (--scope project).
With --global, registers for all projects (no scope restriction).

The command will:
1. Add an MCP server configuration to Claude
2. Use project scope (default) or global scope (--global)
3. Enable semantic code search

Example workflows:
  # Project-specific registration:
  cd /path/to/my-project
  ragex start                    # Index the project
  ragex register claude | sh     # Register for this project only
  
  # Global registration:
  ragex register claude --global | sh  # Register for all projects
"""
            return {
                'success': True,
                'stdout': help_text,
                'stderr': '',
                'returncode': 0
            }
        else:
            return {
                'success': False,
                'stdout': '',
                'stderr': f'No help available for target: {target}\n',
                'returncode': 1
            }
    
    def _register_claude(self, is_global: bool = False) -> Dict[str, Any]:
        """Generate claude registration command"""
        # Get the ragex-mcp path - use absolute path
        home = os.environ.get('HOST_HOME', os.path.expanduser('~'))
        ragex_mcp = os.path.join(home, '.local', 'bin', 'ragex-mcp')
        
        # Ensure ragex_mcp path is absolute
        if not ragex_mcp.startswith('/'):
            ragex_mcp = os.path.abspath(ragex_mcp)
        
        # Generate the command
        if is_global:
            # Global registration - no scope
            command = f'claude mcp add ragex {ragex_mcp}'
        else:
            # Project-scoped registration
            command = f'claude mcp add ragex {ragex_mcp} --scope project'
        
        output = f"{command}\n"
        
        return {
            'success': True,
            'stdout': output,
            'stderr': '',
            'returncode': 0
        }