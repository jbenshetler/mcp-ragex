#!/usr/bin/env python3
"""
RageX Daemon - Long-running process for fast command execution

This daemon keeps models and dependencies loaded in memory to avoid
the cold start penalty on each command execution.
"""

import asyncio
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ragex-daemon')

# Lazy imports to track loading time
LOADED_MODULES = {}

def lazy_import(module_name: str, attribute: Optional[str] = None):
    """Lazy import modules and track loading time"""
    if module_name not in LOADED_MODULES:
        start_time = time.time()
        logger.info(f"Loading {module_name}...")
        
        if attribute:
            module = __import__(module_name, fromlist=[attribute])
            LOADED_MODULES[module_name] = getattr(module, attribute)
        else:
            LOADED_MODULES[module_name] = __import__(module_name)
        
        load_time = time.time() - start_time
        logger.info(f"Loaded {module_name} in {load_time:.2f}s")
    
    return LOADED_MODULES[module_name]


class RagexDaemon:
    """Long-running daemon that handles ragex commands"""
    
    def __init__(self):
        self.running = True
        self.start_time = time.time()
        self.command_count = 0
        self.models_loaded = False
        self.vector_store = None
        self.embedder = None
        self.searcher = None
        
        # Set up signal handlers
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
        
        logger.info("RageX daemon initialized")
    
    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    def _load_models(self):
        """Load models and dependencies lazily"""
        if self.models_loaded:
            return
        
        logger.info("Loading models and dependencies...")
        start_time = time.time()
        
        try:
            # Import heavy dependencies
            EmbeddingManager = lazy_import('src.embedding_manager', 'EmbeddingManager')
            CodeVectorStore = lazy_import('src.vector_store', 'CodeVectorStore')
            RipgrepSearcher = lazy_import('src.server', 'RipgrepSearcher')
            PatternMatcher = lazy_import('src.pattern_matcher', 'PatternMatcher')
            
            # Initialize components
            self.embedder = EmbeddingManager()
            
            # Check if index exists
            project_data_dir = os.environ.get('RAGEX_PROJECT_DATA_DIR', '/data/projects/default')
            chroma_dir = Path(project_data_dir) / 'chroma_db'
            
            if chroma_dir.exists():
                self.vector_store = CodeVectorStore(persist_directory=str(chroma_dir))
                logger.info(f"Loaded vector store from {chroma_dir}")
            
            # Initialize search components
            pattern_matcher = PatternMatcher()
            self.searcher = RipgrepSearcher(pattern_matcher)
            
            self.models_loaded = True
            load_time = time.time() - start_time
            logger.info(f"All models loaded in {load_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Failed to load models: {e}", exc_info=True)
    
    def handle_command(self, command: str, args: list) -> Dict[str, Any]:
        """Handle a command and return the result"""
        self.command_count += 1
        logger.info(f"Handling command: {command} {args}")
        
        try:
            # Load models on first real command (not status checks)
            if command not in ['status', 'health'] and not self.models_loaded:
                self._load_models()
            
            # Route to appropriate handler
            if command == 'status':
                return self._handle_status()
            elif command == 'health':
                return {'status': 'healthy', 'uptime': time.time() - self.start_time}
            elif command == 'search':
                return self._handle_search(args)
            elif command == 'index':
                return self._handle_index(args)
            else:
                # For other commands, execute them via subprocess
                return self._handle_subprocess_command(command, args)
            
        except Exception as e:
            logger.error(f"Error handling command {command}: {e}", exc_info=True)
            return {'error': str(e), 'success': False}
    
    def _handle_status(self) -> Dict[str, Any]:
        """Return daemon status information"""
        uptime = time.time() - self.start_time
        return {
            'status': 'running',
            'uptime_seconds': uptime,
            'uptime_human': f"{uptime/3600:.1f} hours",
            'commands_processed': self.command_count,
            'models_loaded': self.models_loaded,
            'pid': os.getpid(),
            'memory_usage_mb': self._get_memory_usage()
        }
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB"""
        try:
            import psutil
            process = psutil.Process(os.getpid())
            return process.memory_info().rss / 1024 / 1024
        except:
            return 0.0
    
    def _handle_search(self, args: list) -> Dict[str, Any]:
        """Handle search command using loaded components"""
        # This would integrate with the search client
        # For now, delegate to subprocess
        return self._handle_subprocess_command('search', args)
    
    def _handle_index(self, args: list) -> Dict[str, Any]:
        """Handle index command"""
        # Delegate to the indexing script
        return self._handle_subprocess_command('index', args)
    
    def _handle_subprocess_command(self, command: str, args: list) -> Dict[str, Any]:
        """Execute command via subprocess (for commands not yet integrated)"""
        import subprocess
        
        # Map commands to their scripts
        command_map = {
            'search': ['python', 'ragex_search.py'] + args,
            'index': ['python', 'scripts/build_semantic_index.py'] + args,
            'init': ['python', '-c', 'from src.lib.ignore.init import init_ignore_file; from pathlib import Path; init_ignore_file(Path("/workspace"))'],
            'serve': ['python', '-m', 'src.server'],
            'register': ['bash', '/entrypoint.sh', 'register'] + args,
        }
        
        if command in command_map:
            cmd = command_map[command]
        else:
            # Default: try to run via entrypoint
            cmd = ['bash', '/entrypoint.sh', command] + args
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=os.environ.copy()
            )
            
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def run(self):
        """Main daemon loop"""
        logger.info("RageX daemon starting...")
        
        # Create a file to indicate daemon is ready
        Path('/tmp/ragex_daemon_ready').touch()
        
        while self.running:
            # In a real implementation, this would listen on a socket or stdin
            # For now, just sleep and wait for signals
            await asyncio.sleep(1)
        
        logger.info("RageX daemon shutting down...")
        # Clean up ready file
        Path('/tmp/ragex_daemon_ready').unlink(missing_ok=True)


async def main():
    """Main entry point for daemon"""
    daemon = RagexDaemon()
    
    # If running interactively (for entrypoint.sh integration)
    if sys.stdin.isatty():
        # Just run the daemon
        await daemon.run()
    else:
        # Read commands from stdin (for docker exec integration)
        logger.info("Reading commands from stdin...")
        
        # Start daemon in background
        daemon_task = asyncio.create_task(daemon.run())
        
        # Read and process commands
        try:
            while daemon.running:
                try:
                    line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
                    if not line:
                        break
                    
                    # Parse command
                    try:
                        cmd_data = json.loads(line.strip())
                        command = cmd_data.get('command')
                        args = cmd_data.get('args', [])
                    except json.JSONDecodeError:
                        # Simple format: command arg1 arg2 ...
                        parts = line.strip().split()
                        if not parts:
                            continue
                        command = parts[0]
                        args = parts[1:]
                    
                    # Handle command
                    result = daemon.handle_command(command, args)
                    
                    # Return result
                    print(json.dumps(result))
                    sys.stdout.flush()
                    
                except Exception as e:
                    logger.error(f"Error processing command: {e}")
                    print(json.dumps({'error': str(e), 'success': False}))
                    sys.stdout.flush()
        
        finally:
            daemon.running = False
            await daemon_task


if __name__ == '__main__':
    asyncio.run(main())