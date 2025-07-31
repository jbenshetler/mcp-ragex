#!/usr/bin/env python3
"""Admin CLI runner for ragex commands"""

import sys
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.daemon.handlers.ls import LsHandler
from src.daemon.handlers.rm import RmHandler
from src.daemon.handlers.register import RegisterHandler
from src.daemon.handlers.unregister import UnregisterHandler


async def main():
    if len(sys.argv) < 2:
        print("Error: command required", file=sys.stderr)
        sys.exit(1)
    
    command = sys.argv[1]
    args = sys.argv[2:]
    
    handler = None
    if command == 'ls':
        handler = LsHandler({})
    elif command == 'rm':
        handler = RmHandler({})
    elif command == 'register':
        handler = RegisterHandler({})
    elif command == 'unregister':
        handler = UnregisterHandler({})
    else:
        print(f"Error: Unknown command: {command}", file=sys.stderr)
        sys.exit(1)
    
    result = await handler.handle(args)
    
    if result['stdout']:
        print(result['stdout'], end='')
    if result['stderr']:
        print(result['stderr'], end='', file=sys.stderr)
    
    sys.exit(result['returncode'])


if __name__ == '__main__':
    asyncio.run(main())