"""
Init handler for socket daemon.
"""
from typing import Dict, Any
from pathlib import Path
import logging

logger = logging.getLogger('init-handler')


class InitHandler:
    """Handles init commands"""
    
    def __init__(self, shared_modules: Dict[str, Any]):
        self.shared_modules = shared_modules
        self.init_module = None
    
    async def handle(self, args: list) -> Dict[str, Any]:
        """Handle init command"""
        try:
            # Lazy load init module
            if not self.init_module:
                from src.ragex_core.ignore.init import init_ignore_file
                self.init_module = init_ignore_file
            
            # Run init
            self.init_module(Path('/workspace'))
            
            return {
                'success': True,
                'stdout': '✅ .mcpignore file created\n',
                'stderr': '',
                'returncode': 0
            }
        except Exception as e:
            logger.error(f"Init error: {e}", exc_info=True)
            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'returncode': 1
            }