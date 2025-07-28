#!/usr/bin/env python3
"""
Build semantic search index for the codebase.
Run this before starting the MCP server for the first time or when you need to rebuild the index.

Usage:
    uv run build_semantic_index.py . --stats
    uv run build_semantic_index.py /path/to/project --force --stats
"""
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "sentence-transformers>=2.2.0",
#     "chromadb>=0.4.0",
#     "tqdm>=4.65.0",
#     "numpy>=1.24.0",
#     "tree-sitter>=0.20.0,<0.24.0",
#     "tree-sitter-python>=0.20.0",
#     "tree-sitter-javascript>=0.20.0",
#     "tree-sitter-typescript>=0.20.0",
#     "pathspec>=0.11.0",
# ]
# ///

import asyncio
import sys
import time
from pathlib import Path
from datetime import datetime
import json
import argparse
import logging

# Add parent directory to path to find coderagmcp modules
script_dir = Path(__file__).parent
coderagmcp_dir = script_dir.parent

# Change to the coderagmcp directory so relative imports work
import os
original_cwd = os.getcwd()
os.chdir(str(coderagmcp_dir))

# Add both the coderagmcp directory and src to path
sys.path.insert(0, str(coderagmcp_dir))
sys.path.insert(0, str(coderagmcp_dir / "src"))

try:
    from src.indexer import CodeIndexer
    from src.pattern_matcher import PatternMatcher
except ImportError as e:
    print(f"❌ Cannot import required modules from coderagmcp directory.")
    print(f"   Script location: {script_dir}")
    print(f"   CodeRAG directory: {coderagmcp_dir}")
    print(f"   Error: {e}")
    print(f"   Make sure the coderagmcp directory contains src/indexer.py and src/pattern_matcher.py")
    os.chdir(original_cwd)
    sys.exit(1)

from tqdm import tqdm

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("build-index")

# Enable debug logging for pattern matcher only
pattern_logger = logging.getLogger("pattern-matcher")
pattern_logger.setLevel(logging.INFO)  # Changed from DEBUG to reduce noise


async def main():
    parser = argparse.ArgumentParser(description="Build semantic search index for code")
    parser.add_argument("paths", nargs="*", default=["."], 
                       help="Paths to index (default: current directory)")
    parser.add_argument("--force", action="store_true", 
                       help="Force rebuild even if index exists")
    parser.add_argument("--stats", action="store_true", 
                       help="Show detailed statistics after indexing")
    parser.add_argument("--persist-dir", 
                       default=os.getenv('RAGEX_CHROMA_PERSIST_DIR', './chroma_db'),
                       help="Directory for ChromaDB storage (default: $RAGEX_CHROMA_PERSIST_DIR or ./chroma_db)")
    parser.add_argument("--model", default=None,
                       help="Sentence transformer model to use (deprecated, use --preset)")
    parser.add_argument("--preset", choices=["fast", "balanced", "accurate"], default="fast",
                       help="Model preset: fast, balanced, or accurate (default: fast)")
    args = parser.parse_args()
    
    print("🔍 CodeRAG Semantic Search Indexer")
    print("=" * 50)
    
    # Resolve paths relative to the original working directory
    resolved_paths = [str((Path(original_cwd) / p).resolve()) for p in args.paths]
    print(f"📁 Indexing paths: {', '.join(resolved_paths)}")
    
    # Check if index exists (relative to original working directory)
    index_path = Path(original_cwd) / args.persist_dir
    metadata_path = index_path / "index_metadata.json"
    
    if index_path.exists() and not args.force:
        print("⚠️  Index already exists. Use --force to rebuild.")
        
        # Load and show existing index info
        if metadata_path.exists():
            try:
                with open(metadata_path) as f:
                    metadata = json.load(f)
                print(f"\n📊 Current index:")
                print(f"   - Created: {metadata.get('created_at', 'Unknown')}")
                print(f"   - Symbols: {metadata.get('symbol_count', 'Unknown')}")
                print(f"   - Files: {metadata.get('file_count', 'Unknown')}")
                print(f"   - Index time: {metadata.get('index_time', 0):.1f}s")
                
                # Check if paths are different
                indexed_paths = metadata.get('paths', [])
                if set(resolved_paths) != set(indexed_paths):
                    print(f"\n⚠️  Warning: Current index was built from different paths:")
                    print(f"   - Indexed: {', '.join(indexed_paths)}")
                    print(f"   - Requested: {', '.join(resolved_paths)}")
            except Exception as e:
                logger.warning(f"Could not read metadata: {e}")
        
        response = input("\nRebuild anyway? (y/N): ")
        if response.lower() != 'y':
            print("Aborted.")
            os.chdir(original_cwd)
            return
    
    # Initialize indexer
    print("\n📚 Initializing indexer...")
    
    # Handle model/preset selection
    if args.model:
        print(f"   - Model: {args.model} (deprecated, use --preset)")
        print(f"   - Storage: {args.persist_dir}")
        indexer = CodeIndexer(
            persist_directory=str(index_path),
            model_name=args.model
        )
    else:
        print(f"   - Preset: {args.preset}")
        print(f"   - Storage: {args.persist_dir}")
        
        # Check for environment override
        env_model = os.getenv("RAGEX_EMBEDDING_MODEL")
        if env_model:
            print(f"   - Environment override: RAGEX_EMBEDDING_MODEL={env_model}")
        
        indexer = CodeIndexer(
            persist_directory=str(index_path),
            config=args.preset
        )
    
    try:
        # Configure pattern matcher to use original working directory for .mcpignore
        indexer.pattern_matcher.set_working_directory(original_cwd)
        print(f"   - Indexer pattern matcher working directory: {indexer.pattern_matcher.working_directory}")
        print(f"   - Indexer pattern matcher patterns: {len(indexer.pattern_matcher.patterns)}")
        
        # Show model info
        print(f"   - Model: {indexer.config.model_name}")
        print(f"   - Dimensions: {indexer.config.dimensions}")
    except Exception as e:
        print(f"❌ Failed to initialize indexer: {e}")
        os.chdir(original_cwd)
        return
    
    # Count files first
    pattern_matcher = PatternMatcher()
    pattern_matcher.set_working_directory(original_cwd)
    
    # Show exclusion info
    mcpignore_path = Path(original_cwd) / ".mcpignore"
    if mcpignore_path.exists():
        print(f"\n📋 Found .mcpignore with {len(pattern_matcher.patterns)} total exclusion patterns")
        # Count how many patterns are from .mcpignore vs defaults
        default_count = len(pattern_matcher.DEFAULT_EXCLUSIONS)
        mcpignore_count = len(pattern_matcher.patterns) - default_count
        print(f"   - Default patterns: {default_count}")
        print(f"   - .mcpignore patterns: {mcpignore_count}")
        print(f"   - Working directory: {original_cwd}")
        print(f"   - Sample patterns: {pattern_matcher.patterns[:5]}")
    else:
        print(f"\n📋 No .mcpignore found, using {len(pattern_matcher.patterns)} default exclusion patterns")
    
    print("\n🔎 Discovering files...")
    
    all_files = indexer.find_code_files(resolved_paths)
    print(f"📁 Found {len(all_files)} files to index")
    
    # Quick verification - count manually to compare
    manual_count = 0
    for path_str in resolved_paths:
        path = Path(path_str)
        for ext in indexer.supported_extensions:
            for file_path in path.rglob(f"*{ext}"):
                if not pattern_matcher.should_exclude(str(file_path)):
                    manual_count += 1
    
    if manual_count != len(all_files):
        print(f"⚠️  Warning: Manual count ({manual_count}) differs from indexer count ({len(all_files)})")
    else:
        print(f"✅ File count verified: {manual_count} files")
    
    # Show file breakdown by type
    file_types = {}
    for file in all_files:
        ext = file.suffix
        file_types[ext] = file_types.get(ext, 0) + 1
    
    print("\n📊 File breakdown:")
    for ext, count in sorted(file_types.items()):
        print(f"   - {ext}: {count} files")
    
    if not all_files:
        print("\n❌ No files found to index!")
        print("   Make sure you're in a directory with Python, JavaScript, or TypeScript files.")
        os.chdir(original_cwd)
        return
    
    # Start indexing
    print("\n🏗️  Building index...")
    start_time = time.time()
    
    # Track progress
    processed_files = []
    failed_files = []
    
    async def progress_callback(file_path, status):
        if status == "success":
            processed_files.append(file_path)
        else:
            failed_files.append(file_path)
    
    # Index with progress
    try:
        result = await indexer.index_codebase(
            paths=resolved_paths,
            force=True,
            progress_callback=progress_callback
        )
    except Exception as e:
        print(f"\n❌ Indexing failed: {e}")
        logger.exception("Indexing error")
        os.chdir(original_cwd)
        return
    
    elapsed = time.time() - start_time
    
    # Save metadata
    metadata = {
        "created_at": datetime.now().isoformat(),
        "paths": resolved_paths,
        "file_count": result.get("files_processed", 0),
        "symbol_count": result.get("symbols_indexed", 0),
        "index_time": elapsed,
        "model": indexer.config.model_name,
        "model_preset": args.preset if not args.model else "custom",
        "model_dimensions": indexer.config.dimensions,
        "excluded_patterns": pattern_matcher.patterns[:10] if pattern_matcher.patterns else [],
        "total_excluded_patterns": len(pattern_matcher.patterns)
    }
    
    index_path.mkdir(exist_ok=True)
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    # Print summary
    print(f"\n✅ Indexing complete!")
    print(f"\n📊 Summary:")
    print(f"   - Status: {result.get('status', 'unknown')}")
    print(f"   - Files processed: {result.get('files_processed', 0)}")
    print(f"   - Symbols indexed: {result.get('symbols_indexed', 0)}")
    print(f"   - Failed files: {len(result.get('failed_files', []))}")
    print(f"   - Time taken: {elapsed:.1f}s")
    
    if result.get('symbols_indexed', 0) > 0:
        print(f"   - Symbols/second: {result['symbols_indexed']/elapsed:.1f}")
    
    print(f"   - Index location: {index_path.absolute()}")
    
    # Show failed files if any
    if result.get('failed_files'):
        print(f"\n⚠️  Failed to process {len(result['failed_files'])} files:")
        for f in result['failed_files'][:5]:
            print(f"   - {f}")
        if len(result['failed_files']) > 5:
            print(f"   ... and {len(result['failed_files']) - 5} more")
    
    # Show detailed statistics if requested
    if args.stats and result.get('symbols_indexed', 0) > 0:
        print(f"\n📈 Detailed statistics:")
        try:
            stats = await indexer.get_index_statistics()
            print(f"   - Functions: {stats.get('function_count', 0)}")
            print(f"   - Classes: {stats.get('class_count', 0)}")
            print(f"   - Methods: {stats.get('method_count', 0)}")
            print(f"   - Variables: {stats.get('variable_count', 0)}")
            print(f"   - Unique files: {stats.get('unique_files', 0)}")
            print(f"   - Index size: {stats.get('index_size_mb', 0):.1f} MB")
            
            # Language breakdown
            if stats.get('languages'):
                print(f"\n📝 Language breakdown:")
                for lang, count in sorted(stats['languages'].items()):
                    print(f"   - {lang}: {count} symbols")
        except Exception as e:
            logger.warning(f"Could not get detailed stats: {e}")
    
    print(f"\n💡 Next steps:")
    print(f"   1. Start the MCP server: cd {coderagmcp_dir} && ./run_server.sh")
    print(f"   2. Use semantic_search in Claude Code")
    print(f"   3. Re-run this script when codebase changes significantly")
    
    # Download model if needed
    if result.get('symbols_indexed', 0) > 0:
        print(f"\n📦 Note: The sentence transformer model '{indexer.config.model_name}'")
        print(f"   has been downloaded and cached.")
        if args.preset == "fast" or indexer.config.model_name.endswith("all-MiniLM-L6-v2"):
            print(f"   Model size: ~80MB (fast preset)")
        elif args.preset == "balanced" or indexer.config.model_name.endswith("all-mpnet-base-v2"):
            print(f"   Model size: ~420MB (balanced preset)")
        elif args.preset == "accurate" or indexer.config.model_name.endswith("all-roberta-large-v1"):
            print(f"   Model size: ~1.3GB (accurate preset)")
        else:
            print(f"   Model size varies by model")
    
    # Restore original working directory
    os.chdir(original_cwd)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        os.chdir(original_cwd)
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        os.chdir(original_cwd)
        sys.exit(1)