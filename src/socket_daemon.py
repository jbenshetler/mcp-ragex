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
        
        logger.info("RageX socket daemon initialized")
    
    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    
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