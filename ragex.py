#!/usr/bin/env python3
"""
RAGex - Smart code search with project isolation and MCP support

This Python implementation replaces the bash ragex script with:
- Robust argument parsing using argparse
- Integrated MCP server support with --mcp flag
- Better error handling and debugging
"""

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

__version__ = "2.0.0"  # Python implementation version


class RagexCLI:
    """Main RAGex CLI implementation"""
    
    def __init__(self):
        self.docker_image = os.environ.get('RAGEX_DOCKER_IMAGE', 'ragex:local')
        self.user_id = os.getuid()
        self.group_id = os.getgid()
        self.debug = os.environ.get('RAGEX_DEBUG', '').lower() in ('true', '1', 'yes')
        self.embedding_model = os.environ.get('RAGEX_EMBEDDING_MODEL', 'fast')
        
        # Workspace path - will be set based on command
        self.workspace_path = Path.cwd()
        
        # Project identifiers - computed after workspace is determined
        self._project_id = None
        self._project_name = None
        self._daemon_container_name = None
        self._user_volume = None
    
    @property
    def project_id(self) -> str:
        """Get or compute project ID"""
        if self._project_id is None:
            self._project_id = self.generate_project_id(self.workspace_path)
        return self._project_id
    
    @property
    def project_name(self) -> str:
        """Get project name (basename of workspace)"""
        if self._project_name is None:
            self._project_name = self.workspace_path.name
        return self._project_name
    
    @property
    def daemon_container_name(self) -> str:
        """Get daemon container name"""
        if self._daemon_container_name is None:
            self._daemon_container_name = f"ragex_daemon_{self.project_id}"
        return self._daemon_container_name
    
    @property
    def user_volume(self) -> str:
        """Get user volume name"""
        if self._user_volume is None:
            self._user_volume = f"ragex_user_{self.user_id}"
        return self._user_volume
    
    def debug_print(self, message: str):
        """Print debug message if debug mode is enabled"""
        if self.debug:
            print(f"[DEBUG] {message}", file=sys.stderr)
    
    def generate_project_id(self, workspace_path: Path) -> str:
        """Generate consistent project ID based on user and absolute path"""
        abs_path = workspace_path.resolve()
        project_hash = hashlib.sha256(
            f"{self.user_id}:{abs_path}".encode()
        ).hexdigest()[:16]
        return f"ragex_{self.user_id}_{project_hash}"
    
    def is_daemon_running(self) -> bool:
        """Check if daemon container is running"""
        result = subprocess.run(
            ['docker', 'ps', '-q', '-f', f'name={self.daemon_container_name}'],
            capture_output=True,
            text=True
        )
        return bool(result.stdout.strip())
    
    def start_daemon(self) -> bool:
        """Start daemon container if not already running"""
        if self.is_daemon_running():
            self.debug_print(f"Daemon already running: {self.daemon_container_name}")
            return True
        
        print(f"🚀 Starting ragex daemon for {self.project_name}...")
        
        # Docker run command for daemon
        docker_cmd = [
            'docker', 'run', '-d',
            '--name', self.daemon_container_name,
            '-u', f'{self.user_id}:{self.group_id}',
            '-v', f'{self.user_volume}:/data',
            '-v', f'{self.workspace_path}:/workspace:ro',
            '-e', f'WORKSPACE_PATH={self.workspace_path}',
            '-e', f'PROJECT_NAME={self.project_id}',
            '-e', f'RAGEX_EMBEDDING_MODEL={self.embedding_model}',
            '-e', f'HOST_HOME={Path.home()}',
            self.docker_image,
            'daemon'
        ]
        
        self.debug_print(f"Starting daemon: {' '.join(docker_cmd)}")
        
        result = subprocess.run(docker_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ Failed to start daemon: {result.stderr}")
            return False
        
        # Wait for daemon to be ready (check for socket)
        print("⏳ Waiting for daemon to be ready...")
        for i in range(10):
            time.sleep(1)
            check_result = subprocess.run(
                ['docker', 'exec', self.daemon_container_name, 
                 'test', '-S', '/tmp/ragex.sock'],
                capture_output=True
            )
            if check_result.returncode == 0:
                print("✅ Socket daemon is ready")
                return True
        
        # If we get here, daemon failed to start properly
        print("❌ Daemon container is running but socket not found")
        self.show_daemon_logs(tail=20)
        self.stop_daemon()
        return False
    
    def stop_daemon(self) -> bool:
        """Stop daemon container"""
        if not self.is_daemon_running():
            print(f"ℹ️  No daemon running for {self.project_name}")
            return True
        
        print("🛑 Stopping ragex daemon...")
        subprocess.run(['docker', 'stop', self.daemon_container_name], 
                      capture_output=True)
        subprocess.run(['docker', 'rm', self.daemon_container_name], 
                      capture_output=True)
        print("✅ Daemon stopped")
        return True
    
    def show_daemon_logs(self, tail: Optional[int] = None):
        """Show daemon container logs"""
        cmd = ['docker', 'logs', self.daemon_container_name]
        if tail:
            cmd.extend(['--tail', str(tail)])
        subprocess.run(cmd)
    
    def exec_via_daemon(self, cmd: str, args: List[str], 
                       use_tty: bool = True) -> int:
        """Execute command via daemon using socket client"""
        # Start daemon if not running
        if not self.is_daemon_running():
            if not self.start_daemon():
                return 1
        
        # Determine docker exec flags
        exec_flags = ['-i']
        if use_tty and sys.stdin.isatty() and cmd not in ['serve', 'search']:
            exec_flags.append('-t')
        
        # Build docker exec command
        docker_cmd = ['docker', 'exec'] + exec_flags + [
            self.daemon_container_name,
            'python', '-m', 'src.socket_client', cmd
        ] + args
        
        self.debug_print(f"Executing: {' '.join(docker_cmd)}")
        
        result = subprocess.run(docker_cmd)
        return result.returncode
    
    def parse_args(self) -> argparse.Namespace:
        """Parse command line arguments"""
        parser = argparse.ArgumentParser(
            description='RAGex - Smart code search with project isolation',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=self.get_usage_examples()
        )
        
        # Check for --mcp flag before creating subparsers
        if '--mcp' in sys.argv:
            # Minimal parsing for MCP mode
            parser.add_argument('--mcp', action='store_true', 
                              help='Run as MCP server')
            return parser.parse_args(['--mcp'])
        
        subparsers = parser.add_subparsers(dest='command', help='Commands')
        
        # Index command
        index_parser = subparsers.add_parser('index', 
            help='Build semantic index and start daemon')
        index_parser.add_argument('path', nargs='?', default='.', 
            help='Path to index (default: current directory)')
        index_parser.add_argument('--force', action='store_true',
            help='Force rebuild of index')
        index_parser.add_argument('-v', '--verbose', action='store_true',
            help='Show verbose output including debug logs')
        
        # Search command
        search_parser = subparsers.add_parser('search', 
            help='Search in current project')
        search_parser.add_argument('query', help='Search query')
        search_parser.add_argument('--limit', type=int, default=50,
            help='Maximum results (default: 50)')
        search_parser.add_argument('--symbol', action='store_true',
            help='Symbol search mode')
        search_parser.add_argument('--regex', action='store_true',
            help='Regex search mode')
        search_parser.add_argument('--json', action='store_true',
            help='Output results as JSON')
        
        # Bash command
        bash_parser = subparsers.add_parser('bash', 
            help='Get shell in container')
        
        # Init command
        init_parser = subparsers.add_parser('init',
            help='Create .mcpignore file in current directory')
        
        # Stop command
        stop_parser = subparsers.add_parser('stop',
            help='Stop daemon if running')
        
        # Status command
        status_parser = subparsers.add_parser('status',
            help='Check daemon status')
        
        # List projects command
        ls_parser = subparsers.add_parser('ls',
            help='List all projects for current user')
        subparsers.add_parser('list-projects', 
            help='List all projects (alias for ls)')
        
        # Remove project command
        rm_parser = subparsers.add_parser('rm',
            help='Remove project data')
        rm_parser.add_argument('project', help='Project ID to remove')
        clean_parser = subparsers.add_parser('clean-project',
            help='Remove project data (alias for rm)')
        clean_parser.add_argument('project', help='Project ID to remove')
        
        # Info command
        info_parser = subparsers.add_parser('info',
            help='Show project information')
        
        # Log command
        log_parser = subparsers.add_parser('log',
            help='Show/follow daemon logs')
        log_parser.add_argument('project', nargs='?',
            help='Project name/ID (omit for global logs)')
        log_parser.add_argument('-f', '--follow', action='store_true',
            help='Follow log output')
        log_parser.add_argument('--tail', type=int, metavar='N',
            help='Number of lines to show from the end')
        log_parser.add_argument('-t', '--timestamps', action='store_true',
            help='Show timestamps')
        
        # Register/unregister commands
        register_parser = subparsers.add_parser('register',
            help='Show registration instructions')
        register_parser.add_argument('target', 
            help='Registration target (e.g., claude, gemini)')
        unregister_parser = subparsers.add_parser('unregister',
            help='Show unregistration instructions')
        unregister_parser.add_argument('target',
            help='Unregistration target (e.g., claude, gemini)')
        
        # Serve command (legacy, shows deprecation warning)
        serve_parser = subparsers.add_parser('serve',
            help='Start MCP server (deprecated - use --mcp flag)')
        
        return parser.parse_args()
    
    def get_usage_examples(self) -> str:
        """Get usage examples for help text"""
        return """
Quick Start:
  1. ragex index .              # Index your project (starts daemon automatically)
  2. ragex search "query"       # Search your codebase

Examples:
  ragex index .                    # Index current directory
  ragex search "auth functions"    # Search current project
  ragex search "def.*test" --regex # Regex search
  ragex search "handleSubmit" --symbol # Symbol search
  ragex ls                         # Show all your projects
  ragex log mcp-ragex -f           # Follow logs for specific project
  ragex --mcp                      # Run as MCP server for Claude

Environment Variables:
  RAGEX_EMBEDDING_MODEL    Embedding model preset (fast/balanced/accurate)
  RAGEX_PROJECT_NAME       Override project name
  RAGEX_DOCKER_IMAGE       Docker image to use
  RAGEX_DEBUG              Enable debug output
"""
    
    def run(self) -> int:
        """Main entry point"""
        # Special handling for --mcp mode
        if '--mcp' in sys.argv:
            return self.run_mcp_mode()
        
        # Parse arguments
        args = self.parse_args()
        
        # Show help if no command
        if not args.command:
            subprocess.run([sys.argv[0], '--help'])
            return 0
        
        # Update workspace path for index command
        if args.command == 'index' and hasattr(args, 'path'):
            self.workspace_path = Path(args.path).resolve()
        
        # Route to command handlers
        handler_name = f'cmd_{args.command.replace("-", "_")}'
        handler = getattr(self, handler_name, None)
        
        if handler:
            return handler(args)
        else:
            print(f"❌ Error: Unknown command '{args.command}'")
            print(f"\nRun '{sys.argv[0]} --help' for usage")
            return 1
    
    # Command handlers
    def cmd_index(self, args: argparse.Namespace) -> int:
        """Handle index command"""
        print(f"📚 Indexing {self.workspace_path}")
        # Inside container, the workspace is always mounted at /workspace
        container_path = '/workspace'
        cmd_args = [container_path]
        if args.force:
            cmd_args.append('--force')
        if hasattr(args, 'verbose') and args.verbose:
            cmd_args.append('--verbose')
        return self.exec_via_daemon('index', cmd_args)
    
    def cmd_search(self, args: argparse.Namespace) -> int:
        """Handle search command"""
        cmd_args = [args.query]
        
        if args.limit != 50:
            cmd_args.extend(['--limit', str(args.limit)])
        if args.symbol:
            cmd_args.append('--symbol')
        if args.regex:
            cmd_args.append('--regex')
        if args.json:
            cmd_args.append('--json')
        
        return self.exec_via_daemon('search', cmd_args, use_tty=not args.json)
    
    def cmd_bash(self, args: argparse.Namespace) -> int:
        """Handle bash command"""
        return self.exec_via_daemon('bash', [])
    
    def cmd_init(self, args: argparse.Namespace) -> int:
        """Handle init command"""
        return self.exec_via_daemon('init', [])
    
    def cmd_stop(self, args: argparse.Namespace) -> int:
        """Handle stop command"""
        return 0 if self.stop_daemon() else 1
    
    def cmd_status(self, args: argparse.Namespace) -> int:
        """Handle status command"""
        if self.is_daemon_running():
            print(f"✅ Daemon is running for {self.project_name}")
            result = subprocess.run(
                ['docker', 'ps', '-f', f'name={self.daemon_container_name}',
                 '--format', 'table {{.ID}}\t{{.Status}}\t{{.Names}}']
            )
            return 0
        else:
            print(f"❌ No daemon running for {self.project_name}")
            return 1
    
    def cmd_info(self, args: argparse.Namespace) -> int:
        """Handle info command"""
        print("🔧 RageX Project Information")
        print(f"   User ID: {self.user_id}")
        print(f"   Workspace: {self.workspace_path}")
        print(f"   Project ID: {self.project_id}")
        print(f"   Project Name: {self.project_name}")
        print(f"   User Volume: {self.user_volume}")
        print(f"   Docker Image: {self.docker_image}")
        print(f"   Embedding Model: {self.embedding_model}")
        print()
        return self.cmd_status(args)
    
    def cmd_ls(self, args: argparse.Namespace) -> int:
        """Handle ls/list-projects command"""
        return self._run_admin_command('list-projects')
    
    def cmd_list_projects(self, args: argparse.Namespace) -> int:
        """Alias for ls command"""
        return self.cmd_ls(args)
    
    def cmd_rm(self, args: argparse.Namespace) -> int:
        """Handle rm/clean-project command"""
        return self._run_admin_command('clean-project', [args.project])
    
    def cmd_clean_project(self, args: argparse.Namespace) -> int:
        """Alias for rm command"""
        return self.cmd_rm(args)
    
    def cmd_register(self, args: argparse.Namespace) -> int:
        """Handle register command"""
        return self._run_admin_command('register', [args.target])
    
    def cmd_unregister(self, args: argparse.Namespace) -> int:
        """Handle unregister command"""
        return self._run_admin_command('unregister', [args.target])
    
    def cmd_serve(self, args: argparse.Namespace) -> int:
        """Handle legacy serve command"""
        print("⚠️  Warning: 'ragex serve' is deprecated")
        print("   Use 'ragex --mcp' instead for MCP server mode")
        print("   Daemons are now started automatically with 'ragex index'")
        return 1
    
    def cmd_log(self, args: argparse.Namespace) -> int:
        """Handle log command"""
        if args.project:
            # Project-specific logs
            return self._show_project_logs(args.project, args)
        else:
            # Global logs
            return self._show_global_logs(args)
    
    def _run_admin_command(self, command: str, args: List[str] = None) -> int:
        """Run administrative commands that don't need workspace"""
        docker_cmd = [
            'docker', 'run', '--rm',
            '-u', f'{self.user_id}:{self.group_id}',
            '-v', f'{self.user_volume}:/data',
            '-e', 'PROJECT_NAME=admin',
            '-e', f'HOST_HOME={Path.home()}',
            '-e', f'HOST_USER={os.environ.get("USER", "unknown")}',
            '-e', f'WORKSPACE_PATH={self.workspace_path}',
            self.docker_image,
            command
        ]
        
        if args:
            docker_cmd.extend(args)
        
        self.debug_print(f"Running admin command: {' '.join(docker_cmd)}")
        result = subprocess.run(docker_cmd)
        return result.returncode
    
    def _show_project_logs(self, project_identifier: str, 
                          args: argparse.Namespace) -> int:
        """Show logs for specific project"""
        # Resolve project name to ID
        resolve_result = subprocess.run(
            ['docker', 'run', '--rm',
             '-v', f'{self.user_volume}:/data',
             '--entrypoint', 'python',
             self.docker_image,
             '-m', 'src.ragex_core.project_resolver', project_identifier],
            capture_output=True,
            text=True
        )
        
        if resolve_result.returncode != 0:
            error_msg = resolve_result.stderr.strip()
            if error_msg.startswith("ERROR: "):
                print(f"❌ {error_msg[7:]}")
            else:
                print(f"❌ Failed to resolve project: {project_identifier}")
            return 1
        
        project_id = resolve_result.stdout.strip()
        container_name = f"ragex_daemon_{project_id}"
        
        # Check if container exists
        check_result = subprocess.run(
            ['docker', 'ps', '-q', '-f', f'name={container_name}'],
            capture_output=True,
            text=True
        )
        
        if not check_result.stdout.strip():
            print(f"❌ No running daemon found for project: {project_identifier}")
            if project_identifier != project_id:
                print(f"   (Resolved to: {project_id})")
            return 1
        
        # Show logs
        if project_identifier != project_id:
            print(f"📋 Logs for project: {project_identifier} [{project_id}]")
        else:
            print(f"📋 Logs for project: {project_id}")
        
        log_cmd = ['docker', 'logs', container_name]
        if args.follow:
            log_cmd.append('--follow')
        if args.tail:
            log_cmd.extend(['--tail', str(args.tail)])
        if args.timestamps:
            log_cmd.append('--timestamps')
        
        result = subprocess.run(log_cmd)
        return result.returncode
    
    def _show_global_logs(self, args: argparse.Namespace) -> int:
        """Show logs from all daemon containers"""
        # Find all daemon containers
        result = subprocess.run(
            ['docker', 'ps', '--format', '{{.Names}}'],
            capture_output=True,
            text=True
        )
        
        daemon_containers = [
            name for name in result.stdout.strip().split('\n')
            if name.startswith('ragex_daemon_')
        ]
        
        if not daemon_containers:
            print("📋 No ragex daemon containers are currently running")
            print("\nStart a daemon with: ragex index")
            return 0
        
        print("📋 Global ragex logs from all daemon containers:\n")
        
        for container in sorted(daemon_containers):
            project_id = container.replace('ragex_daemon_', '')
            print(f"=== {project_id} ===")
            
            log_cmd = ['docker', 'logs', container, '--tail', '10']
            if args.timestamps:
                log_cmd.append('--timestamps')
            
            # Show first 20 lines of output
            result = subprocess.run(log_cmd, capture_output=True, text=True)
            lines = result.stdout.split('\n')[:20]
            print('\n'.join(lines))
            print()
        
        return 0
    
    def run_mcp_mode(self) -> int:
        """Run as MCP server bridging to daemon"""
        self.debug_print("Starting MCP server mode")
        
        # Ensure daemon is running
        if not self.is_daemon_running():
            if not self.start_daemon():
                return 1
        
        # Start continuous indexing to ensure ChromaDB exists
        print("📚 Starting continuous indexing...", file=sys.stderr)
        # Inside container, the workspace is always mounted at /workspace
        container_path = '/workspace'
        result = self.exec_via_daemon('start_continuous_index', [container_path])
        if result != 0:
            print("⚠️  Warning: Failed to start continuous indexing", file=sys.stderr)
        
        # Run MCP server inside the container where dependencies are available
        self.debug_print("Running MCP server in container")
        
        # Use exec_via_daemon but without TTY for stdio mode
        docker_cmd = ['docker', 'exec', '-i',  # -i for interactive, no -t for MCP stdio
                      self.daemon_container_name,
                      'python', '-m', 'src.socket_client', 'mcp']
        
        self.debug_print(f"Executing MCP server: {' '.join(docker_cmd)}")
        
        # Run the MCP server command
        result = subprocess.run(docker_cmd)
        return result.returncode


def main():
    """Main entry point"""
    cli = RagexCLI()
    sys.exit(cli.run())


if __name__ == '__main__':
    main()