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
            
            if target == 'claude':
                return self._register_claude()
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
            help_text = """Usage: ragex register claude [--help]

Outputs a shell command to register this project with Claude.
The output is designed to be piped to sh or used with eval:

  ragex register claude | sh
  eval "$(ragex register claude)"

This will register the MCP server for the current project directory
with Claude, enabling code search from Claude.

The command will:
1. Add an MCP server configuration to Claude
2. Use the current project path as the scope
3. Enable semantic code search for this project

Example workflow:
  cd /path/to/my-project
  ragex start                    # Index the project
  ragex register claude | sh     # Register with Claude
  # Now Claude can search your project code
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
    
    def _register_claude(self) -> Dict[str, Any]:
        """Generate claude registration command"""
        # Get the ragex-mcp path
        home = os.environ.get('HOST_HOME', os.path.expanduser('~'))
        ragex_mcp = os.path.join(home, '.local', 'bin', 'ragex-mcp')
        
        # Shell-escape paths
        escaped_ragex = shlex.quote(ragex_mcp)
        escaped_workspace = shlex.quote(self.workspace_path)
        
        # Generate the command
        command = f'claude mcp add ragex {escaped_ragex} --scope {escaped_workspace}'
        
        output = f"{command}\n"
        
        return {
            'success': True,
            'stdout': output,
            'stderr': '',
            'returncode': 0
        }