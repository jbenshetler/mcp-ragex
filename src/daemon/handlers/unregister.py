#!/usr/bin/env python3
"""Handler for unregister command"""

import logging
import os
import shlex
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


class UnregisterHandler:
    """Handles unregister commands with --help support"""
    
    def __init__(self, shared_modules: Dict[str, Any]):
        self.shared_modules = shared_modules
        self.workspace_path = os.environ.get('WORKSPACE_PATH', '/workspace')
        
    async def handle(self, args: list) -> Dict[str, Any]:
        """Handle unregister command"""
        try:
            if not args:
                return {
                    'success': False,
                    'stdout': '',
                    'stderr': 'Error: Unregistration target required (e.g., claude)\n',
                    'returncode': 1
                }
            
            target = args[0]
            
            # Check for --help flag
            if '--help' in args:
                return self._show_help(target)
            
            if target == 'claude':
                return self._unregister_claude()
            else:
                return {
                    'success': False,
                    'stdout': '',
                    'stderr': f'Error: Unknown unregistration target: {target}\n',
                    'returncode': 1
                }
                
        except Exception as e:
            logger.error(f"Unregister error: {e}", exc_info=True)
            return {
                'success': False,
                'stdout': '',
                'stderr': f"Error: {str(e)}\n",
                'returncode': 1
            }
    
    def _show_help(self, target: str) -> Dict[str, Any]:
        """Show detailed help for unregister command"""
        if target == 'claude':
            help_text = """Usage: ragex unregister claude [--help]

Outputs a shell command to unregister this project from Claude.
The output is designed to be piped to sh or used with eval:

  ragex unregister claude | sh
  eval "$(ragex unregister claude)"

This will remove the MCP server registration for the current project
directory from Claude.

The command will:
1. Remove the MCP server configuration from Claude
2. Use the current project path to identify which config to remove
3. Disable code search for this project in Claude

Example workflow:
  cd /path/to/my-project
  ragex unregister claude | sh   # Remove from Claude
  # Claude can no longer search this project
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
    
    def _unregister_claude(self) -> Dict[str, Any]:
        """Generate claude unregistration command"""
        # Shell-escape workspace path
        escaped_workspace = shlex.quote(self.workspace_path)
        
        # Generate the command
        command = f'claude mcp remove ragex --scope {escaped_workspace}'
        
        output = f"{command}\n"
        
        return {
            'success': True,
            'stdout': output,
            'stderr': '',
            'returncode': 0
        }