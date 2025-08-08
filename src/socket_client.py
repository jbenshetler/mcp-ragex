#!/usr/bin/env python3
"""
Socket client for communicating with RAGex daemon

This lightweight client sends commands to the socket daemon and returns results.
"""

import json
import socket
import sys
import os

SOCKET_PATH = "/tmp/ragex.sock"
BUFFER_SIZE = 65536  # Initial buffer size
MAX_RESPONSE_SIZE = 10 * 1024 * 1024  # 10MB maximum response


def send_command(command: str, args: list) -> dict:
    """Send a command to the daemon and return the result"""
    
    # Create Unix domain socket
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    
    try:
        # Connect to daemon
        client.connect(SOCKET_PATH)
        
        # Prepare request
        request = {
            'command': command,
            'args': args
        }
        
        # Send request
        client.send(json.dumps(request).encode('utf-8'))
        
        # Receive response (handle large responses by reading in chunks)
        data_chunks = []
        total_size = 0
        
        while True:
            chunk = client.recv(BUFFER_SIZE)
            if not chunk:
                break
            data_chunks.append(chunk)
            total_size += len(chunk)
            
            # Safety check to prevent memory exhaustion
            if total_size > MAX_RESPONSE_SIZE:
                return {
                    'success': False,
                    'error': f'Response too large: {total_size} bytes (max: {MAX_RESPONSE_SIZE})'
                }
            
            # Check if we have a complete JSON response
            full_data = b''.join(data_chunks)
            try:
                response = json.loads(full_data.decode('utf-8'))
                return response
            except json.JSONDecodeError:
                # Not a complete JSON yet, continue reading
                continue
        
        # If we get here, connection was closed without complete response
        if not data_chunks:
            return {
                'success': False,
                'error': 'No response from daemon'
            }
        
        # Try to parse what we have
        full_data = b''.join(data_chunks)
        try:
            response = json.loads(full_data.decode('utf-8'))
            return response
        except json.JSONDecodeError as e:
            return {
                'success': False,
                'error': f'Invalid JSON response: {str(e)}'
            }
        
    except FileNotFoundError:
        print(f"Socket not found at {SOCKET_PATH}", file=sys.stderr)
        return {
            'success': False,
            'error': f'Daemon not running (socket not found at {SOCKET_PATH})'
        }
    except ConnectionRefusedError:
        return {
            'success': False,
            'error': 'Daemon not accepting connections'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Socket error: {str(e)}'
        }
    finally:
        client.close()


def main():
    """Main entry point for command-line usage"""
    if len(sys.argv) < 2:
        print("Usage: socket_client.py <command> [args...]", file=sys.stderr)
        sys.exit(1)
    
    command = sys.argv[1]
    args = sys.argv[2:]
    
    # Special handling for serve command - it needs direct stdio
    if command == 'serve':
        # For serve, we need to exec the server directly
        os.execvp('python', ['python', '-m', 'src.server'] + args)
        # Should not reach here
        sys.exit(1)
    
    # Special handling for mcp command - it needs direct stdio
    if command == 'mcp':
        # For MCP, we need to exec the MCP server directly
        os.execvp('python', ['python', '-m', 'src.server'] + args)
        # Should not reach here
        sys.exit(1)
    
    # Send command to daemon
    result = send_command(command, args)
    
    # Handle response
    if result.get('success'):
        # Print stdout if present
        if result.get('stdout'):
            print(result['stdout'], end='')
        
        # Print stderr to stderr if present
        if result.get('stderr'):
            print(result['stderr'], end='', file=sys.stderr)
        
        # Exit with the command's return code
        sys.exit(result.get('returncode', 0))
    else:
        # Error occurred
        error = result.get('error', 'Unknown error')
        print(f"Error: {error}", file=sys.stderr)
        
        # If stderr is present, print it too
        if result.get('stderr'):
            print(result['stderr'], end='', file=sys.stderr)
        
        sys.exit(result.get('returncode', 1))


if __name__ == '__main__':
    main()