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
            
            # Check for --global flag
            is_global = '--global' in args
            
            if target == 'claude':
                return self._unregister_claude(is_global)
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
            help_text = """Usage: ragex unregister claude [--global] [--help]

Outputs a shell command to unregister ragex from Claude.
The output is designed to be piped to sh or used with eval:

  ragex unregister claude | sh          # Project-scoped
  ragex unregister claude --global | sh # Global

Options:
  --global    Unregister globally instead of project-scoped

By default, unregisters for the current project only (--scope project).
With --global, unregisters the global configuration.

The command will:
1. Remove the MCP server configuration from Claude
2. Use project scope (default) or global scope (--global)
3. Disable code search for the specified scope

Example workflows:
  # Project-specific unregistration:
  cd /path/to/my-project
  ragex unregister claude | sh     # Remove for this project only
  
  # Global unregistration:
  ragex unregister claude --global | sh  # Remove for all projects
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
    
    def _unregister_claude(self, is_global: bool = False) -> Dict[str, Any]:
        """Generate claude unregistration command"""
        # Generate the command
        if is_global:
            # Global unregistration - no scope
            command = 'claude mcp remove ragex'
        else:
            # Project-scoped unregistration
            command = 'claude mcp remove ragex --scope project'
        
        output = f"{command}\n"
        
        return {
            'success': True,
            'stdout': output,
            'stderr': '',
            'returncode': 0
        }