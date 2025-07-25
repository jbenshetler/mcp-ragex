#!/usr/bin/env python3
"""
Example implementation of 'ragex init' command

This demonstrates how the init command would be integrated into the main ragex CLI.
In production, this would be part of the main ragex command structure.
"""

import sys
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ignore import init_ignore_file, IGNORE_FILENAME


def main():
    parser = argparse.ArgumentParser(
        prog='ragex init',
        description=f'Initialize {IGNORE_FILENAME} with sensible defaults for MCP-RageX'
    )
    
    parser.add_argument(
        'path',
        nargs='?',
        default='.',
        help='Directory where to create .mcpignore (default: current directory)'
    )
    
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Overwrite existing .mcpignore file'
    )
    
    parser.add_argument(
        '--minimal', '-m',
        action='store_true',
        help='Create minimal .mcpignore with essential patterns only'
    )
    
    parser.add_argument(
        '--add', '-a',
        action='append',
        dest='patterns',
        help='Add custom pattern (can be used multiple times)'
    )
    
    args = parser.parse_args()
    
    # Validate path
    path = Path(args.path).resolve()
    if not path.exists():
        print(f"Error: Directory '{path}' does not exist")
        return 1
    
    if not path.is_dir():
        print(f"Error: '{path}' is not a directory")
        return 1
    
    # Create .mcpignore file
    try:
        created = init_ignore_file(
            path=path,
            force=args.force,
            minimal=args.minimal,
            custom_patterns=args.patterns
        )
        
        ignore_path = path / IGNORE_FILENAME
        
        if created:
            print(f"✅ Created {ignore_path}")
            if args.minimal:
                print("   Generated minimal .mcpignore file with essential patterns")
            else:
                print("   Generated comprehensive .mcpignore with default exclusions")
            if args.patterns:
                print(f"   Added {len(args.patterns)} custom patterns")
            print()
            print("Next steps:")
            print(f"1. Review and customize {IGNORE_FILENAME} as needed")
            print("2. Add project-specific patterns")
            print("3. Create additional .mcpignore files in subdirectories if needed")
        else:
            print(f"❌ {ignore_path} already exists")
            print(f"   Use --force to overwrite the existing file")
            return 1
            
    except Exception as e:
        print(f"Error creating {IGNORE_FILENAME}: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())