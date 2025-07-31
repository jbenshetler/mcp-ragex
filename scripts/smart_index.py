#!/usr/bin/env python3
"""
Smart indexing with file-level checksum verification and incremental updates.

This script implements true incremental indexing by:
1. Storing checksums for individual files (not workspace-level)
2. Comparing file checksums to detect exactly what changed
3. Only re-indexing files that actually changed
4. Avoiding prompts and double file reads
"""

import sys
import os
import argparse
import logging
from pathlib import Path
from datetime import datetime
from src.ragex_core.project_utils import get_chroma_db_path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('smart-index')

# Add parent directory to path
script_dir = Path(__file__).parent
ragex_dir = script_dir.parent
sys.path.insert(0, str(ragex_dir))

try:
    from src.ragex_core.file_checksum import scan_workspace_files, compare_checksums
    from src.ragex_core.project_utils import (
        find_existing_project_root, 
        generate_project_id,
        load_project_metadata,
        update_project_metadata
    )
    from src.ragex_core.pattern_matcher import PatternMatcher
    from src.ragex_core.vector_store import CodeVectorStore
    from src.indexer import CodeIndexer
except ImportError as e:
    print(f"❌ Failed to import required modules: {e}")
    sys.exit(1)


async def run_full_index(workspace_path: Path, args) -> bool:
    """Run full indexing using build_semantic_index.py"""
    import subprocess
    
    index_args = [sys.executable, str(ragex_dir / "scripts" / "build_semantic_index.py")]
    index_args.append(str(workspace_path))
    index_args.append('--force')  # Always force for initial index
    
    # Pass through arguments
    if args.stats:
        index_args.append('--stats')
    if args.verbose:
        index_args.append('--verbose')
    
    # Run the indexer
    result = subprocess.run(index_args, env=os.environ.copy())
    return result.returncode == 0


async def run_incremental_update(workspace_path: Path, project_data_dir: str, 
                                ignore_manager, args) -> bool:
    """Run incremental update based on file checksum comparison"""
    
    try:
        # Initialize vector store to get stored checksums
        vector_store = CodeVectorStore(persist_directory=str(get_chroma_db_path(project_data_dir)))
        stored_checksums = vector_store.get_file_checksums()
        
        if not stored_checksums:
            if not args.quiet:
                print("⚠️  No stored checksums found, running full index...")
            return await run_full_index(workspace_path, args)
        
        # Scan current workspace files
        if not args.quiet:
            print("🔍 Scanning workspace for changes...")
        
        current_checksums = scan_workspace_files(workspace_path, ignore_manager)
        
        # Compare checksums to find changes
        added, removed, modified = compare_checksums(current_checksums, stored_checksums)
        
        if not (added or removed or modified):
            if not args.quiet:
                print("✅ Index is up-to-date")
                metadata = load_project_metadata(generate_project_id(str(workspace_path), 
                                                os.environ.get('DOCKER_USER_ID', str(os.getuid()))))
                if metadata:
                    files_indexed = len(stored_checksums)
                    last_indexed = metadata.get('index_completed_at', 'unknown')
                    print(f"   Files: {files_indexed}")
                    print(f"   Last indexed: {last_indexed}")
            return True
        
        # Perform incremental update
        if not args.quiet:
            print(f"📝 Updating index: +{len(added)} ~{len(modified)} -{len(removed)} files")
        
        # Initialize indexer
        indexer = CodeIndexer(persist_directory=str(get_chroma_db_path(project_data_dir)))
        
        # Remove deleted files
        for file_path in removed:
            deleted_count = vector_store.delete_by_file(file_path)
            if args.verbose:
                print(f"   Removed {deleted_count} symbols from {file_path}")
        
        # Update modified and new files
        changed_files = added + modified
        if changed_files:
            # Convert to Path objects
            file_paths = [workspace_path / file_path for file_path in changed_files]
            
            # Create checksums dict for efficient passing
            file_checksums = {str(workspace_path / file_path): current_checksums[file_path] 
                            for file_path in changed_files}
            
            # Perform incremental update
            result = await indexer.update_files(file_paths, file_checksums)
            
            if args.verbose:
                print(f"   Updated {result['files_processed']} files")
                print(f"   Added {result['symbols_indexed']} symbols")
                if result['failed_files']:
                    print(f"   Failed: {result['failed_files']}")
        
        # Update project metadata
        project_id = generate_project_id(str(workspace_path), 
                                       os.environ.get('DOCKER_USER_ID', str(os.getuid())))
        
        metadata = {
            'files_indexed': len(current_checksums),
            'index_completed_at': datetime.now().isoformat(),
            'incremental_update': True,
            'files_added': len(added),
            'files_modified': len(modified), 
            'files_removed': len(removed)
        }
        update_project_metadata(project_id, metadata)
        
        if not args.quiet:
            print("✅ Index updated successfully")
            
        return True
        
    except Exception as e:
        print(f"❌ Incremental update failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return False


def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description='Smart semantic indexing with file-level checksums')
    parser.add_argument('path', nargs='?', default='.', help='Path to index')
    parser.add_argument('--force', action='store_true', help='Force full re-indexing')
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
    
    # For project ID generation, we MUST use the host workspace path
    # to ensure consistency between host and container
    host_workspace_path = os.environ.get('WORKSPACE_PATH')
    if not host_workspace_path:
        error_msg = (
            "WORKSPACE_PATH environment variable not set. "
            "This should be set by the ragex wrapper script. "
            "Cannot proceed without proper path mapping."
        )
        logger.error(error_msg)
        print(f"❌ {error_msg}")
        sys.exit(1)
    
    logger.info(f"Container workspace: {workspace_path}")
    logger.info(f"Host workspace: {host_workspace_path}")
    
    # Check for existing project root using host path
    project_root = find_existing_project_root(Path(host_workspace_path), user_id)
    
    if project_root and project_root != workspace_path:
        # We're in a subdirectory of an existing project
        if not args.quiet:
            print(f"📍 Detected existing project index at: {project_root}")
            print(f"🔄 Using project root for indexing...")
        # Update host workspace path but keep container path as /workspace
        host_workspace_path = str(project_root)
        # workspace_path remains as container path (/workspace)
    
    # Generate project ID using HOST path for consistency
    project_id = generate_project_id(host_workspace_path, user_id)
    project_data_dir = f'/data/projects/{project_id}'
    
    logger.info(f"Generated project ID: {project_id}")
    logger.info(f"Project data directory: {project_data_dir}")
    
    # Initialize pattern matcher for ignore handling
    pattern_matcher = PatternMatcher()
    pattern_matcher.set_working_directory(str(workspace_path))
    ignore_manager = pattern_matcher._ignore_manager
    
    # Check if index exists
    index_exists = (Path(project_data_dir) / 'chroma_db').exists()
    
    async def run_indexing():
        if not index_exists or args.force:
            # First time or forced - run full index
            if not args.quiet:
                reason = "forced rebuild" if args.force else "no existing index"
                print(f"📊 Creating full index ({reason})")
            
            success = await run_full_index(workspace_path, args)
            if not success:
                print("❌ Full indexing failed")
                return False
        else:
            # Incremental update
            success = await run_incremental_update(workspace_path, project_data_dir, 
                                                 ignore_manager, args)
            if not success:
                return False
        
        return True
    
    # Run the indexing
    import asyncio
    success = asyncio.run(run_indexing())
    
    if not success:
        sys.exit(1)
    
    if not args.quiet:
        print("🚀 Indexing complete")


if __name__ == "__main__":
    main()