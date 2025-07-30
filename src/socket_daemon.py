#!/usr/bin/env python3
"""
RageX Socket Daemon - High-performance command executor

This daemon accepts commands via Unix domain socket and executes them
using subprocess for stability.
"""

import asyncio
import json
import logging
import os
import signal
import socket
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ragex-socket-daemon')

# Import watchdog components
try:
    from src.watchdog_monitor import WatchdogMonitor, WATCHDOG_AVAILABLE
except ImportError:
    WATCHDOG_AVAILABLE = False
    WatchdogMonitor = None

# Import file watching components
from src.ragex_core.indexing_queue import IndexingQueue
from src.ragex_core.indexing_file_handler import IndexingFileHandler
from src.ragex_core.pattern_matcher import PatternMatcher

# Socket configuration
SOCKET_PATH = "/tmp/ragex.sock"
BUFFER_SIZE = 65536


class RagexSocketDaemon:
    """Socket-based daemon that handles ragex commands with pre-loaded modules"""
    
    def __init__(self):
        self.running = True
        self.start_time = time.time()
        self.command_count = 0
        self.handlers = {}
        self.shared_modules = {}
        
        # Set up signal handlers
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
        
        # Initialize file watching components
        self.watchdog_monitor = None
        self.indexing_queue = None
        self.pattern_matcher = None
        self._setup_file_watching()
        
        logger.info("RageX socket daemon initialized")
    
    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
        
        # Stop file watching
        if self.watchdog_monitor and self.watchdog_monitor.is_running():
            self.watchdog_monitor.stop()
        
        # Shutdown indexing queue
        if self.indexing_queue:
            asyncio.create_task(self.indexing_queue.shutdown())
    
    def _setup_file_watching(self):
        """Set up file watching for automatic re-indexing"""
        if not WATCHDOG_AVAILABLE:
            logger.warning("Watchdog not available, file watching disabled")
            return
            
        try:
            # Initialize pattern matcher for ignore handling
            workspace_path = Path("/workspace")
            if not workspace_path.exists():
                logger.warning("Workspace directory not found, file watching disabled")
                return
                
            self.pattern_matcher = PatternMatcher()
            self.pattern_matcher.set_working_directory(str(workspace_path))
            ignore_manager = self.pattern_matcher._ignore_manager
            
            # NOTE: We'll initialize the queue and observer later when we have an event loop
            self.indexing_queue = None
            self._file_observer = None
            self._workspace_path = workspace_path
            self._ignore_manager = ignore_manager
            
            logger.info("File watching setup deferred until event loop is running")
            
        except Exception as e:
            logger.error(f"Failed to setup file watching: {e}", exc_info=True)
    
    async def _start_file_watching(self):
        """Start file watching after event loop is running"""
        if not WATCHDOG_AVAILABLE or not hasattr(self, '_workspace_path'):
            return
            
        try:
            # Create indexing queue with callback
            self.indexing_queue = IndexingQueue(
                debounce_seconds=60.0,
                on_index_callback=self._handle_incremental_index
            )
            
            # Create file handler and pass the current event loop
            file_handler = IndexingFileHandler(self._ignore_manager, self.indexing_queue)
            # Store the main event loop reference
            import threading
            threading.main_thread()._loop = asyncio.get_running_loop()
            
            # Create and start watchdog observer
            from watchdog.observers import Observer
            observer = Observer()
            observer.schedule(file_handler, str(self._workspace_path), recursive=True)
            observer.start()
            
            # Store observer for cleanup
            self._file_observer = observer
            
            logger.info("👁️  File watching enabled (60s debounce)")
            logger.info(f"   Watching: {self._workspace_path}")
            
        except Exception as e:
            logger.error(f"Failed to start file watching: {e}", exc_info=True)
    
    async def _handle_incremental_index(self, added_files: list, removed_files: list, file_checksums: dict):
        """Handle incremental indexing of changed files"""
        try:
            # Import indexer lazily
            from src.indexer import CodeIndexer
            
            # Get project data directory
            project_data_dir = os.environ.get('RAGEX_PROJECT_DATA_DIR')
            if not project_data_dir:
                project_name = os.environ.get('PROJECT_NAME', 'admin')
                project_data_dir = f'/data/projects/{project_name}'
            
            # Create indexer instance
            indexer = CodeIndexer(
                persist_directory=f"{project_data_dir}/chroma_db"
            )
            
            # Update files
            symbol_count = 0
            
            # Remove deleted files first
            for file_path in removed_files:
                try:
                    indexer.vector_store.delete_by_file(str(file_path))
                    logger.info(f"   Removed from index: {file_path}")
                except Exception as e:
                    logger.error(f"   Failed to remove {file_path}: {e}")
            
            # Re-index changed/added files
            if added_files:
                # Convert file paths to strings and map checksums
                file_checksums_str = {}
                for file_path in added_files:
                    file_path_str = str(file_path)
                    if file_path in file_checksums:
                        file_checksums_str[file_path_str] = file_checksums[file_path]
                
                result = await indexer.update_files(added_files, file_checksums_str)
                symbol_count = result.get('symbols_indexed', 0)
            
            logger.info(f"✅ Re-indexed {len(added_files)} files ({symbol_count} symbols)")
            
        except Exception as e:
            logger.error(f"Incremental indexing failed: {e}", exc_info=True)
            raise
    
    
    async def handle_request(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle a single request from a client"""
        addr = writer.get_extra_info('peername')
        logger.debug(f"New connection from {addr}")
        
        try:
            # Read request
            data = await reader.read(BUFFER_SIZE)
            if not data:
                return
            
            # Parse request
            try:
                request = json.loads(data.decode('utf-8'))
                command = request.get('command')
                args = request.get('args', [])
                
                logger.info(f"Handling command: {command} {args}")
                self.command_count += 1
                
                # Execute command
                result = await self.execute_command(command, args)
                
                # Send response
                response = json.dumps(result).encode('utf-8')
                writer.write(response)
                await writer.drain()
                
            except json.JSONDecodeError as e:
                error_response = json.dumps({
                    'success': False,
                    'error': f'Invalid JSON: {e}'
                }).encode('utf-8')
                writer.write(error_response)
                await writer.drain()
                
        except Exception as e:
            logger.error(f"Error handling request: {e}", exc_info=True)
            try:
                error_response = json.dumps({
                    'success': False,
                    'error': str(e)
                }).encode('utf-8')
                writer.write(error_response)
                await writer.drain()
            except:
                pass
        
        finally:
            writer.close()
            await writer.wait_closed()
    
    async def execute_command(self, command: str, args: list) -> Dict[str, Any]:
        """Execute a command using pre-loaded modules"""
        try:
            if command == 'status':
                return self._get_status()
            
            elif command == 'search':
                # Check if index exists first
                project_data_dir = os.environ.get('RAGEX_PROJECT_DATA_DIR')
                if not project_data_dir:
                    project_name = os.environ.get('PROJECT_NAME', 'admin')
                    project_data_dir = f'/data/projects/{project_name}'
                
                chroma_path = Path(project_data_dir) / 'chroma_db'
                if not chroma_path.exists():
                    return {
                        'success': False,
                        'stdout': '',
                        'stderr': "❌ No index found. Run 'ragex index .' first\n",
                        'returncode': 1
                    }
                
                return await self._handle_search(args)
            
            elif command == 'index':
                return await self._handle_index(args)
            
            elif command == 'init':
                return await self._handle_init(args)
            
            elif command == 'serve':
                return await self._handle_serve(args)
            
            else:
                # Unknown command
                return {
                    'success': False,
                    'stdout': '',
                    'stderr': f"❌ Error: Unknown command '{command}'\n\nRun 'ragex help' or 'ragex --help' to see available commands.\n",
                    'returncode': 1
                }
            
        except Exception as e:
            logger.error(f"Error executing command {command}: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'traceback': str(e.__traceback__)
            }
    
    def _get_status(self) -> Dict[str, Any]:
        """Return daemon status"""
        uptime = time.time() - self.start_time
        return {
            'success': True,
            'status': 'running',
            'uptime_seconds': uptime,
            'uptime_human': f"{uptime/3600:.1f} hours",
            'commands_processed': self.command_count,
            'pid': os.getpid(),
        }
    
    async def _handle_search(self, args: list) -> Dict[str, Any]:
        """Handle search command using pre-loaded handler"""
        # Get or create search handler
        if 'search' not in self.handlers:
            from src.daemon.handlers.search import SearchHandler
            self.handlers['search'] = SearchHandler(self.shared_modules)
        
        return await self.handlers['search'].handle(args)
    
    async def _handle_index(self, args: list) -> Dict[str, Any]:
        """Handle index command"""
        import subprocess
        import sys
        
        cmd = [sys.executable, '/app/scripts/smart_index.py'] + args
        
        # Log the command being executed
        logger.info(f"Executing index command: {' '.join(cmd)}")
        
        # Check if script exists
        script_path = '/app/scripts/smart_index.py'
        if not os.path.exists(script_path):
            logger.error(f"Script not found: {script_path}")
            return {
                'success': False,
                'error': f'Script not found: {script_path}',
                'stderr': f'Script not found: {script_path}\n',
                'stdout': '',
                'returncode': 1
            }
        
        env = os.environ.copy()
        env['PYTHONPATH'] = '/app:' + env.get('PYTHONPATH', '')
        env['RAGEX_WORKING_DIR'] = '/workspace'  # Tell the script to use /workspace as working dir
        env['DOCKER_USER_ID'] = os.environ.get('DOCKER_USER_ID', str(os.getuid()))  # Pass user ID for project detection
        
        try:
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            stdout, stderr = await result.communicate()
            
            stdout_text = stdout.decode('utf-8')
            stderr_text = stderr.decode('utf-8')
            
            # Log output for debugging
            if stderr_text:
                logger.error(f"Index command stderr: {stderr_text}")
            if result.returncode != 0:
                logger.error(f"Index command failed with code {result.returncode}")
                
            response = {
                'success': result.returncode == 0,
                'stdout': stdout_text,
                'stderr': stderr_text,
                'returncode': result.returncode
            }
            
            # Add error field for compatibility with socket_client
            if result.returncode != 0:
                error_msg = stderr_text.strip() if stderr_text.strip() else f"Command failed with exit code {result.returncode}"
                response['error'] = error_msg
                
            return response
            
        except Exception as e:
            logger.error(f"Exception running index command: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'stderr': str(e),
                'stdout': '',
                'returncode': 1
            }
    
    async def _handle_init(self, args: list) -> Dict[str, Any]:
        """Handle init command using pre-loaded handler"""
        # Get or create init handler
        if 'init' not in self.handlers:
            from src.daemon.handlers.init import InitHandler
            self.handlers['init'] = InitHandler(self.shared_modules)
        
        return await self.handlers['init'].handle(args)
    
    async def _handle_serve(self, args: list) -> Dict[str, Any]:
        """Handle serve command - start MCP server"""
        import subprocess
        import sys
        
        cmd = [sys.executable, '-m', 'src.server'] + args
        
        env = os.environ.copy()
        env['PYTHONPATH'] = '/app:' + env.get('PYTHONPATH', '')
        
        # For serve, we need to run it interactively
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=False  # Let it use stdin/stdout directly
        )
        
        return {
            'success': result.returncode == 0,
            'returncode': result.returncode
        }
    
    async def _handle_generic_command(self, command: str, args: list) -> Dict[str, Any]:
        """Handle any other command by running it through entrypoint.sh"""
        cmd = ['/entrypoint.sh', command] + args
        
        result = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await result.communicate()
        
        return {
            'success': result.returncode == 0,
            'stdout': stdout.decode('utf-8'),
            'stderr': stderr.decode('utf-8'),
            'returncode': result.returncode
        }
    
    async def run(self):
        """Main daemon loop"""
        # Remove existing socket
        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)
        
        # Start file watching now that event loop is running
        await self._start_file_watching()
        
        # Create Unix domain socket server
        server = await asyncio.start_unix_server(
            self.handle_request,
            path=SOCKET_PATH
        )
        
        # Set socket permissions
        os.chmod(SOCKET_PATH, 0o666)
        
        logger.info(f"Socket daemon listening on {SOCKET_PATH}")
        
        async with server:
            await server.serve_forever()


async def main():
    """Main entry point"""
    daemon = RagexSocketDaemon()
    
    try:
        await daemon.run()
    except KeyboardInterrupt:
        logger.info("Daemon stopped by user")
    except Exception as e:
        logger.error(f"Daemon error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Clean up file observer
        if hasattr(daemon, '_file_observer') and daemon._file_observer:
            daemon._file_observer.stop()
            daemon._file_observer.join(timeout=2)
        
        # Clean up socket
        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)


if __name__ == '__main__':
    asyncio.run(main())