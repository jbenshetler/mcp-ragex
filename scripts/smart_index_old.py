#!/usr/bin/env python3
"""
Smart indexing with checksum verification and project root detection.

This script wraps build_semantic_index.py to add:
- Content-based checksum verification
- Automatic project root detection
- Clear user messaging
"""

import sys
import os
import json
import hashlib
import argparse
from pathlib import Path
from datetime import datetime

# Add parent directory to path
script_dir = Path(__file__).parent
ragex_dir = script_dir.parent
sys.path.insert(0, str(ragex_dir))

try:
    from src.lib.workspace_checksum import calculate_workspace_checksum, get_file_stats
    from src.lib.project_utils import (
        find_existing_project_root, 
        generate_project_id,
        get_project_checksum,
        update_project_checksum,
        load_project_metadata
    )
    from src.lib.pattern_matcher import PatternMatcher
except ImportError as e:
    print(f"❌ Failed to import required modules: {e}")
    sys.exit(1)


def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description='Smart semantic indexing')
    parser.add_argument('path', nargs='?', default='.', help='Path to index')
    parser.add_argument('--force', action='store_true', help='Force re-indexing')
    parser.add_argument('--quiet', action='store_true', help='Suppress informational messages')
    parser.add_argument('--stats', action='store_true', help='Show statistics')
    parser.add_argument('--verbose', action='store_true', help='Show verbose output')
    
    args, unknown_args = parser.parse_known_args()
    
    # Get workspace path
    if args.path == '.':
        workspace_path = Path('/workspace')
    else:
        workspace_path = Path(args.path).resolve()
    
    # Get user ID from environment
    user_id = os.environ.get('DOCKER_USER_ID', str(os.getuid()))
    
    # Check for existing project root
    project_root = find_existing_project_root(workspace_path, user_id)
    
    if project_root and project_root != workspace_path:
        # We're in a subdirectory of an existing project
        if not args.quiet:
            print(f"📍 Detected existing project index at: {project_root}")
            print(f"🔄 Reindexing entire project from root...")
        workspace_path = project_root
    
    # Generate project ID
    project_id = generate_project_id(str(workspace_path), user_id)
    
    # Initialize pattern matcher for ignore handling
    pattern_matcher = PatternMatcher()
    pattern_matcher.set_working_directory(str(workspace_path))
    ignore_manager = pattern_matcher._ignore_manager
    
    # Check if we need to index
    needs_index = args.force
    reason = "forced" if args.force else ""
    
    if not args.force:
        # Calculate current checksum
        if not args.quiet:
            print("🔍 Checking workspace for changes...")
        
        try:
            current_checksum = calculate_workspace_checksum(workspace_path, ignore_manager)
            stored_checksum = get_project_checksum(project_id)
            
            if stored_checksum is None:
                needs_index = True
                reason = "no previous index found"
            elif current_checksum != stored_checksum:
                needs_index = True
                reason = "workspace has changed"
                if args.verbose:
                    print(f"   Current:  {current_checksum[:16]}...")
                    print(f"   Previous: {stored_checksum[:16]}...")
            else:
                # Checksums match
                metadata = load_project_metadata(project_id)
                if metadata:
                    files_indexed = metadata.get('files_indexed', 0)
                    last_indexed = metadata.get('index_completed_at', 'unknown')
                    if not args.quiet:
                        print(f"✅ Index is up-to-date")
                        print(f"   Files: {files_indexed}")
                        print(f"   Last indexed: {last_indexed}")
                else:
                    if not args.quiet:
                        print("✅ Index is up-to-date")
                        
        except Exception as e:
            needs_index = True
            reason = f"checksum calculation failed: {e}"
    
    if not needs_index:
        # Nothing to do
        sys.exit(0)
    
    # Show why we're indexing
    if not args.quiet and reason:
        print(f"📊 Indexing workspace ({reason})")
    
    # Get file stats if requested
    if args.stats:
        stats = get_file_stats(workspace_path, ignore_manager)
        print(f"\n📈 Workspace statistics:")
        print(f"   Total files: {stats['total_files']:,}")
        print(f"   Total size: {stats['total_size']:,} bytes")
        if stats['by_extension']:
            print("   By extension:")
            for ext, info in sorted(stats['by_extension'].items(), 
                                  key=lambda x: x[1]['count'], reverse=True)[:10]:
                print(f"     {ext}: {info['count']} files ({info['size']:,} bytes)")
    
    # Build command for build_semantic_index.py
    index_args = [sys.executable, str(ragex_dir / "scripts" / "build_semantic_index.py")]
    index_args.append(str(workspace_path))
    
    # Pass through arguments
    if args.force:
        index_args.append('--force')
    if args.stats:
        index_args.append('--stats')
    if args.verbose:
        index_args.append('--verbose')
    
    # Add any unknown arguments
    index_args.extend(unknown_args)
    
    # Run the indexer
    import subprocess
    result = subprocess.run(index_args, env=os.environ.copy())
    
    if result.returncode == 0:
        # Update checksum on success
        try:
            # Recalculate to ensure accuracy
            new_checksum = calculate_workspace_checksum(workspace_path, ignore_manager)
            
            # Count files (approximate from stats)
            stats = get_file_stats(workspace_path, ignore_manager)
            files_indexed = stats['total_files']
            
            # Update metadata
            update_project_checksum(project_id, new_checksum, files_indexed)
            
            if args.verbose:
                print(f"\n✅ Updated project checksum: {new_checksum[:16]}...")
                
        except Exception as e:
            print(f"⚠️  Warning: Failed to update project checksum: {e}")
    
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()