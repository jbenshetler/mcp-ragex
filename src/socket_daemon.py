#!/usr/bin/env python3
"""
RageX Socket Daemon - High-performance command executor with pre-loaded modules

This daemon keeps Python modules loaded in memory and accepts commands via
Unix domain socket for near-instant execution.
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

# Socket configuration
SOCKET_PATH = "/tmp/ragex.sock"
BUFFER_SIZE = 65536


class RagexSocketDaemon:
    """Socket-based daemon that handles ragex commands with pre-loaded modules"""
    
    def __init__(self):
        self.running = True
        self.start_time = time.time()
        self.command_count = 0
        self.modules_loaded = False
        
        # Pre-loaded modules and objects
        self.modules = {}
        self.searcher = None
        self.pattern_matcher = None
        
        # Set up signal handlers
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
        
        # Load modules immediately
        self._load_modules()
        
        logger.info("RageX socket daemon initialized")
    
    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    def _load_modules(self):
        """Pre-load all heavy modules at startup"""
        if self.modules_loaded:
            return
        
        logger.info("Loading modules...")
        load_start = time.time()
        
        try:
            # Import heavy dependencies - do it gradually
            logger.info("Loading numpy...")
            import numpy as np
            
            logger.info("Loading chromadb...")
            import chromadb
            
            logger.info("Loading tree_sitter...")
            import tree_sitter
            
            # Skip torch and sentence_transformers for now - they're too heavy
            # They'll be loaded on demand when needed
            
            # Import our lightweight modules
            logger.info("Loading core modules...")
            import src.server
            import src.pattern_matcher
            import src.tree_sitter_enhancer
            import src.ignore.manager
            
            # Store references
            self.modules = {
                'numpy': np,
                'chromadb': chromadb,
                'tree_sitter': tree_sitter,
                'server': src.server,
                'pattern_matcher': src.pattern_matcher,
                'tree_sitter_enhancer': src.tree_sitter_enhancer,
                'ignore_manager': src.ignore.manager,
            }
            
            # Pre-instantiate commonly used objects
            from src.pattern_matcher import PatternMatcher
            from src.server import RipgrepSearcher
            
            self.pattern_matcher = PatternMatcher()
            self.searcher = RipgrepSearcher(self.pattern_matcher)
            
            self.modules_loaded = True
            load_time = time.time() - load_start
            logger.info(f"All modules loaded in {load_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Failed to load modules: {e}", exc_info=True)
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
                return await self._handle_search(args)
            
            elif command == 'index':
                return await self._handle_index(args)
            
            elif command == 'init':
                return await self._handle_init(args)
            
            elif command == 'serve':
                return await self._handle_serve(args)
            
            else:
                # For other commands, execute them directly
                return await self._handle_generic_command(command, args)
            
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
            'modules_loaded': self.modules_loaded,
            'pid': os.getpid(),
        }
    
    async def _handle_search(self, args: list) -> Dict[str, Any]:
        """Handle search command using pre-loaded modules"""
        import io
        import contextlib
        
        # Capture stdout and stderr
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()
        
        try:
            # Redirect stdout/stderr
            with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
                # Import search module if not already loaded
                if 'ragex_search' not in self.modules:
                    import ragex_search
                    self.modules['ragex_search'] = ragex_search
                
                # Set up sys.argv for the search module
                import sys
                old_argv = sys.argv
                try:
                    sys.argv = ['ragex_search.py'] + args
                    
                    # Run the search directly using the module
                    await self.modules['ragex_search'].main()
                    
                    return {
                        'success': True,
                        'stdout': stdout_buffer.getvalue(),
                        'stderr': stderr_buffer.getvalue(),
                        'returncode': 0
                    }
                finally:
                    sys.argv = old_argv
                    
        except SystemExit as e:
            return {
                'success': e.code == 0,
                'stdout': stdout_buffer.getvalue(),
                'stderr': stderr_buffer.getvalue(),
                'returncode': e.code or 0
            }
        except Exception as e:
            return {
                'success': False,
                'stdout': stdout_buffer.getvalue(),
                'stderr': stderr_buffer.getvalue() + f"\nError: {str(e)}",
                'returncode': 1
            }
    
    async def _handle_index(self, args: list) -> Dict[str, Any]:
        """Handle index command"""
        import subprocess
        import sys
        
        cmd = [sys.executable, '/app/scripts/build_semantic_index.py'] + args
        
        env = os.environ.copy()
        env['PYTHONPATH'] = '/app:' + env.get('PYTHONPATH', '')
        env['RAGEX_WORKING_DIR'] = '/workspace'  # Tell the script to use /workspace as working dir
        
        result = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        
        stdout, stderr = await result.communicate()
        
        return {
            'success': result.returncode == 0,
            'stdout': stdout.decode('utf-8'),
            'stderr': stderr.decode('utf-8'),
            'returncode': result.returncode
        }
    
    async def _handle_init(self, args: list) -> Dict[str, Any]:
        """Handle init command"""
        try:
            from src.ignore.init import init_ignore_file
            from pathlib import Path
            
            init_ignore_file(Path('/workspace'))
            
            return {
                'success': True,
                'stdout': '✅ .mcpignore file created\n',
                'stderr': '',
                'returncode': 0
            }
        except Exception as e:
            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'returncode': 1
            }
    
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
        # Clean up socket
        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)


if __name__ == '__main__':
    asyncio.run(main())