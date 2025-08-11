#!/usr/bin/env python3
"""
Indexing queue for batching file changes.

Collects file change events and triggers re-indexing after a debounce period.
"""

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Set, Optional, Callable, List, Dict, Any
from datetime import datetime

from .file_checksum import calculate_file_checksum

logger = logging.getLogger("indexing-queue")


class IndexingQueue:
    """
    Queue for batching file changes before re-indexing.
    
    Collects file modifications/additions/deletions and triggers
    re-indexing after a configurable debounce period.
    """
    
    def __init__(self, 
                 debounce_seconds: float = 60.0,
                 min_index_interval: float = 300.0,  # 5 minutes between indexing runs
                 on_index_callback: Optional[Callable[[List[Path], List[Path], Dict[Path, str]], asyncio.Future]] = None):
        """
        Initialize the indexing queue.
        
        Args:
            debounce_seconds: Time to wait after last change before indexing
            min_index_interval: Minimum time between indexing runs (seconds)
            on_index_callback: Async callback to trigger indexing (added_files, removed_files, file_checksums)
        """
        self.debounce_seconds = debounce_seconds
        self.min_index_interval = min_index_interval
        self.on_index_callback = on_index_callback
        
        # File tracking with checksums
        self._added_files: Set[Path] = set()
        self._removed_files: Set[Path] = set()
        self._file_checksums: Dict[Path, str] = {}  # NEW: Store checksums for added files
        self._last_change_time: float = 0
        self._last_index_completed_time: float = 0
        
        # State
        self._timer_task: Optional[asyncio.Task] = None
        self._indexing: bool = False
        self._lock = asyncio.Lock()
        self._shutdown_requested: bool = False
        self._current_indexing_task: Optional[asyncio.Task] = None
        
    async def add_file(self, file_path: str, checksum: str):
        """Add a file to the indexing queue (created or modified).
        
        Args:
            file_path: Path to the file
            checksum: SHA256 checksum of the file (required)
        """
        async with self._lock:
            path = Path(file_path)
            
            # If file was previously marked for removal, just remove from that set
            if path in self._removed_files:
                self._removed_files.remove(path)
            else:
                self._added_files.add(path)
            
            # Store checksum
            self._file_checksums[path] = checksum
            
            self._last_change_time = time.time()
            logger.info(f"📝 File changed: {file_path}")
            
            # Reset timer
            await self._reset_timer()
    
    async def remove_file(self, file_path: str):
        """Mark a file for removal from index."""
        async with self._lock:
            path = Path(file_path)
            
            # If file was pending addition, just remove from that set
            if path in self._added_files:
                self._added_files.remove(path)
                # Also remove from checksums
                self._file_checksums.pop(path, None)
            else:
                self._removed_files.add(path)
            
            self._last_change_time = time.time()
            logger.info(f"🗑️  File deleted: {file_path}")
            
            # Reset timer
            await self._reset_timer()
    
    async def _reset_timer(self):
        """Reset the debounce timer."""
        # Cancel existing timer
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
        
        # Start new timer
        self._timer_task = asyncio.create_task(self._wait_and_index())
    
    async def _wait_and_index(self):
        """Wait for debounce period then trigger indexing."""
        try:
            # Show waiting message if we have pending changes
            if self._added_files or self._removed_files:
                total_changes = len(self._added_files) + len(self._removed_files)
                logger.info(f"⏱️  Waiting {self.debounce_seconds}s for more changes... ({total_changes} pending)")
            
            # Wait for debounce period
            await asyncio.sleep(self.debounce_seconds)
            
            # Trigger indexing
            await self._trigger_indexing()
            
        except asyncio.CancelledError:
            # Timer was reset, this is normal
            pass
        except Exception as e:
            logger.error(f"Error in indexing timer: {e}", exc_info=True)
    
    async def _trigger_indexing(self):
        """Trigger the indexing callback with collected files."""
        async with self._lock:
            # Check if shutdown requested or already indexing
            if self._shutdown_requested or self._indexing:
                return
            
            # Check if we have changes
            if not self._added_files and not self._removed_files:
                return
            
            # Get files to process
            added_files = list(self._added_files)
            removed_files = list(self._removed_files)
            
            # Clear queues
            self._added_files.clear()
            self._removed_files.clear()
            
            # Mark as indexing
            self._indexing = True
        
        # Create task so we can track it
        self._current_indexing_task = asyncio.create_task(self._do_indexing(added_files, removed_files))
        await self._current_indexing_task
    
    async def _do_indexing(self, added_files: List[Path], removed_files: List[Path]):
        """Actual indexing work with cancellation points"""
        try:
            # Check for shutdown before starting
            if self._shutdown_requested:
                logger.info("Shutdown requested, skipping indexing")
                return
                
            # Log what we're doing
            if added_files and removed_files:
                logger.info(f"🔄 Re-indexing {len(added_files)} changed files, removing {len(removed_files)} deleted files...")
            elif added_files:
                logger.info(f"🔄 Re-indexing {len(added_files)} changed files...")
            elif removed_files:
                logger.info(f"🔄 Removing {len(removed_files)} deleted files from index...")
            else:
                logger.info(f"🔄 Running full index scan...")
            
            start_time = time.time()
            
            # Calculate checksums for added files
            file_checksums = {}
            if added_files:
                for file_path in added_files:
                    # Check for cancellation
                    if asyncio.current_task().cancelled():
                        logger.info("Indexing cancelled during checksum calculation")
                        return
                        
                    if file_path.exists():
                        checksum = calculate_file_checksum(file_path)
                        file_checksums[file_path] = checksum
            
            # Call the indexing callback with checksums
            if self.on_index_callback:
                await self.on_index_callback(added_files, removed_files, file_checksums)
            else:
                logger.warning("No indexing callback configured")
            
            # Log completion
            elapsed = time.time() - start_time
            logger.info(f"✅ Re-indexing complete in {elapsed:.1f}s")
            
        except asyncio.CancelledError:
            logger.info("Indexing cancelled gracefully")
            raise
        except Exception as e:
            logger.error(f"Failed to re-index files: {e}", exc_info=True)
        finally:
            self._indexing = False
            self._last_index_completed_time = time.time()
    
    async def request_index(self, 
                           source: str = "manual", 
                           force: bool = False,
                           quiet: bool = False,
                           stats: bool = False, 
                           verbose: bool = False,
                           name: str = None,
                           path: str = None,
                           model: str = None) -> Dict[str, Any]:
        """Request an index operation with full parameter support
        
        Args:
            source: Source of request ("manual", "continuous", "mcp-startup")
            force: Bypass timing restrictions and force full reindex
            quiet: Suppress informational messages
            stats: Show indexing statistics 
            verbose: Show detailed verbose output
            name: Custom project name (for new projects only)
            path: Custom path to index (defaults to workspace)
            model: Embedding model to use (fast/balanced/accurate/multilingual)
            
        Returns:
            Dict with success status, messages, and statistics
        """
        # Configure logging based on verbosity flags
        self._configure_logging(verbose, quiet)
        
        # Validate model and network access requirements
        if model and model != 'fast':
            # Check if container has network access
            import subprocess
            try:
                result = subprocess.run(
                    ['curl', '--connect-timeout', '2', '-s', 'https://httpbin.org/ip'],
                    capture_output=True,
                    timeout=5
                )
                has_network = result.returncode == 0
            except (subprocess.TimeoutExpired, FileNotFoundError):
                has_network = False
            
            if not has_network:
                error_msg = (f"❌ Model '{model}' requires network access but container has no network access.\n"
                           f"   \n"
                           f"   Available options:\n"
                           f"   1. Use the pre-bundled model: ragex index . --model fast\n"
                           f"   2. Enable network access by reinstalling:\n"
                           f"      install.sh --cpu --network")
                if not quiet:
                    logger.error(error_msg)
                return {
                    'success': False,
                    'stdout': '',
                    'stderr': error_msg + '\n',
                    'returncode': 1
                }
        
        # Check without acquiring lock first (fast path)
        if self._indexing:
            message = f"Index already in progress, skipping {source} request"
            if not quiet:
                logger.info(message)
            return {
                'success': False,
                'stdout': '',
                'stderr': f"{message}\n",
                'returncode': 1
            }
            
        # Skip time check if force flag is set
        if not force:
            time_since_last = time.time() - self._last_index_completed_time
            if time_since_last < self.min_index_interval:
                wait_time = self.min_index_interval - time_since_last
                message = f"Too soon since last index ({wait_time:.0f}s remaining). Use --force to override."
                if not quiet:
                    logger.info(message)
                return {
                    'success': False,
                    'stdout': '',
                    'stderr': f"{message}\n",
                    'returncode': 1
                }
        
        # Now acquire lock and trigger indexing
        async with self._lock:
            # Double-check conditions with lock held
            if self._indexing:
                return {
                    'success': False,
                    'stdout': '',
                    'stderr': 'Index already in progress\n',
                    'returncode': 1
                }
                
            # Reset any pending timer since we're doing it now
            if self._timer_task and not self._timer_task.done():
                self._timer_task.cancel()
                
            # Clear the queues since we're indexing everything
            self._added_files.clear()
            self._removed_files.clear()
            self._file_checksums.clear()
        
        # Call enhanced indexing with parameters
        try:
            result = await self._handle_incremental_index(
                source=source,
                force=force,
                quiet=quiet,
                stats=stats,
                verbose=verbose,
                name=name,
                path=path or '/workspace',
                model=model
            )
            logger.debug(f"Indexing result: {result}")
            formatted_result = self._format_output(result, stats, quiet)
            logger.debug(f"Formatted result: {formatted_result}")
            return formatted_result
        except Exception as e:
            error_msg = f"Indexing failed: {e}"
            logger.error(error_msg, exc_info=True)
            return {
                'success': False,
                'stdout': '',
                'stderr': f"{error_msg}\n",
                'returncode': 1
            }
    
    def get_status(self) -> dict:
        """Get current queue status."""
        return {
            'pending_additions': len(self._added_files),
            'pending_removals': len(self._removed_files),
            'is_indexing': self._indexing,
            'last_change': datetime.fromtimestamp(self._last_change_time).isoformat() if self._last_change_time > 0 else None,
            'last_index_completed': datetime.fromtimestamp(self._last_index_completed_time).isoformat() if self._last_index_completed_time > 0 else None,
            'debounce_seconds': self.debounce_seconds,
            'min_index_interval': self.min_index_interval
        }
    
    def _configure_logging(self, verbose: bool, quiet: bool):
        """Configure logging levels based on verbosity flags"""
        if verbose:
            logger.setLevel(logging.DEBUG)
        elif quiet:
            logger.setLevel(logging.WARNING)
        # else: Don't override - let the global RAGEX_LOG_LEVEL setting take precedence
    
    def _format_output(self, result: Dict, stats: bool, quiet: bool) -> Dict[str, Any]:
        """Format output messages and statistics based on flags"""
        if not result:
            return {
                'success': False,
                'stdout': '',
                'stderr': 'Indexing failed\n',
                'returncode': 1
            }
        
        # Check for error result
        if result.get('success') == False or result.get('error'):
            error_msg = result.get('error', 'Indexing failed')
            return {
                'success': False,
                'stdout': '',
                'stderr': f"{error_msg}\n",
                'returncode': 1
            }
        
        # Format success response - indexer returns various status types
        status = result.get('status', 'complete')
        files_processed = result.get('files_processed', 0)
        symbols_indexed = result.get('symbols_indexed', 0)
        
        output_lines = []
        
        if not quiet:
            if status == "existing":
                output_lines.append("✅ Index is up-to-date")
                if stats:
                    output_lines.append(f"   Files: {files_processed}")
                    output_lines.append(f"   Symbols: {symbols_indexed}")
            elif status in ["complete", "updated"]:
                if stats:
                    output_lines.append(f"✅ Indexed {files_processed} files")
                    output_lines.append(f"   Symbols: {symbols_indexed}")
                    if result.get('files_failed', 0) > 0:
                        output_lines.append(f"   Failed: {result['files_failed']} files")
                else:
                    output_lines.append("Index completed successfully")
            elif status == "no_files":
                output_lines.append("⚠️  No source files found to index")
            elif status == "no_symbols":
                output_lines.append("⚠️  No symbols extracted from files")
            else:
                output_lines.append("Index completed successfully")
        
        return {
            'success': True,
            'stdout': '\n'.join(output_lines) + '\n' if output_lines else '',
            'stderr': '',
            'returncode': 0
        }

    async def _handle_incremental_index(self, 
                                       source: str,
                                       force: bool = False,
                                       quiet: bool = False, 
                                       stats: bool = False,
                                       verbose: bool = False,
                                       name: str = None,
                                       path: str = None,
                                       model: str = None) -> Dict[str, Any]:
        """Enhanced incremental indexing with full parameter support"""
        logger.debug(f"Attempting import at _handle_incremental_index")        
        try:
            # Import indexing components
            from .project_utils import (
                generate_project_id, 
                get_project_data_dir,
                get_chroma_db_path,
                load_project_metadata,
                save_project_metadata,
                update_project_metadata,
                is_project_name_unique,
                find_existing_project_root
            )
            logger.debug(f"Attempting import at _handle_incremental_index of CodeIndexer") 
            from ..indexer import CodeIndexer
            logger.debug(f"Attempting import at _handle_incremental_index of PatternMatcher") 
            from .pattern_matcher import PatternMatcher
            
            # Get user ID from environment
            user_id = os.environ.get('DOCKER_USER_ID', str(os.getuid()))
            
            # For project ID generation, we MUST use the host workspace path
            host_workspace_path = os.environ.get('WORKSPACE_PATH')
            if not host_workspace_path:
                raise ValueError("WORKSPACE_PATH environment variable not set")
            
            # Check for existing project root
            project_root = find_existing_project_root(Path(host_workspace_path), user_id)
            if project_root and str(project_root) != host_workspace_path:
                if not quiet:
                    logger.info(f"📍 Detected existing project index at: {project_root}")
                    logger.info("🔄 Using project root for indexing...")
                host_workspace_path = str(project_root)
            
            # Generate project ID using HOST path for consistency
            project_id = generate_project_id(host_workspace_path, user_id)
            project_data_dir = f'/data/projects/{project_id}'
            
            # Handle project metadata
            existing_metadata = load_project_metadata(project_id)
            
            if existing_metadata:
                existing_name = existing_metadata.get('project_name', existing_metadata.get('workspace_basename'))
                existing_path = existing_metadata.get('workspace_path')
                
                # STRICT: No name changes allowed
                if name and existing_name != name:
                    raise ValueError(f"Project already indexed as '{existing_name}'. Use 'ragex rm {existing_name}' first to re-index with a different name")
                
                # Detect moved directory
                if existing_path != host_workspace_path:
                    if not quiet:
                        logger.info(f"🔄 Detected project moved from: {existing_path} → {host_workspace_path}")
                        logger.info("📦 Clearing old index and re-scanning...")
                    
                    # Clear the entire ChromaDB for this project
                    logger.debug(f"Attempting import at _handle_incremental_index of CodeVectorStore") 
                    from .vector_store import CodeVectorStore
                    chroma_path = get_chroma_db_path(project_data_dir)
                    if chroma_path.exists():
                        vector_store = CodeVectorStore(persist_directory=str(chroma_path))
                        vector_store.clear_all()
                    
                    # Update metadata with new path
                    existing_metadata['workspace_path'] = host_workspace_path
                    update_project_metadata(project_id, existing_metadata)
                    
                    # Force full reindex
                    force = True
                
                project_name = existing_name
                
                # For existing projects, validate model compatibility
                existing_model = existing_metadata.get('embedding_model', 'fast')
                
                # Determine the actual model that will be used (resolve defaults)
                actual_model = model or os.environ.get('RAGEX_EMBEDDING_MODEL', 'fast')
                
                if actual_model != existing_model:
                    # Import here to avoid circular dependency
                    from .embedding_config import EmbeddingConfig
                    
                    try:
                        existing_config = EmbeddingConfig(preset=existing_model)
                        new_config = EmbeddingConfig(preset=actual_model)
                        
                        # Check dimension compatibility
                        if existing_config.dimensions != new_config.dimensions:
                            error_msg = (f"❌ Embedding model mismatch detected!\n"
                                       f"   \n"
                                       f"   Current project model: '{existing_model}' ({existing_config.dimensions} dimensions)\n"
                                       f"   Resolved model:        '{actual_model}' ({new_config.dimensions} dimensions)\n"
                                       f"   \n"
                                       f"   💡 Embedding models with different dimensions cannot be mixed in the same project.\n"
                                       f"   This would corrupt your search results and make them meaningless.\n"
                                       f"   \n"
                                       f"   🔧 Solutions:\n"
                                       f"   1. Keep using current model:  ragex index . --model {existing_model}\n"
                                       f"   2. Force complete rebuild:    ragex index . --model {actual_model} --force\n"
                                       f"   3. Remove and recreate:      ragex rm \"{project_name}\" && ragex index . --model {actual_model}\n"
                                       f"   \n"
                                       f"   ⚠️  Option 2 and 3 will delete all existing embeddings and rebuild from scratch.")
                        else:
                            # Same dimensions but different models - still risky
                            error_msg = (f"❌ Embedding model change detected!\n"
                                       f"   \n"
                                       f"   Current project model: '{existing_model}'\n"
                                       f"   Resolved model:        '{actual_model}'\n"
                                       f"   \n"
                                       f"   ⚠️  Even with same dimensions ({existing_config.dimensions}d), different models\n"
                                       f"   produce different embeddings that cannot be meaningfully compared.\n"
                                       f"   \n"
                                       f"   🔧 Solutions:\n"
                                       f"   1. Keep using current model:  ragex index . --model {existing_model}\n"
                                       f"   2. Force complete rebuild:    ragex index . --model {actual_model} --force\n"
                                       f"   \n"
                                       f"   💡 Use --force only if you want to completely rebuild the index.")
                                       
                    except Exception as config_error:
                        # Fallback to basic error if config loading fails
                        error_msg = (f"❌ Cannot change embedding model from '{existing_model}' to '{actual_model}'\n"
                                   f"   Configuration error: {config_error}\n"
                                   f"   Use --force to rebuild with new model.")
                    
                    if not quiet:
                        logger.error(error_msg)
                    return {
                        'success': False,
                        'stdout': '',
                        'stderr': error_msg + '\n',
                        'returncode': 1
                    }
                
                # If we reach here, models are compatible - use the resolved model
                embedding_model = actual_model
                
                # Update last_accessed for existing projects
                existing_metadata['last_accessed'] = datetime.now().isoformat()
                update_project_metadata(project_id, existing_metadata)
            else:
                # New project
                if name:
                    # Check if name is unique
                    if not is_project_name_unique(name, user_id):
                        raise ValueError(f"Project name '{name}' is already in use. Please choose a different name")
                    project_name = name
                else:
                    # Default to basename
                    project_name = Path(host_workspace_path).name
                
                # For new projects, user can specify model
                embedding_model = model or os.environ.get('RAGEX_EMBEDDING_MODEL', 'fast')
                
                # Save initial metadata with all required fields
                metadata = {
                    'project_name': project_name,
                    'project_id': project_id,
                    'workspace_path': host_workspace_path,
                    'workspace_basename': Path(host_workspace_path).name,
                    'created_at': datetime.now().isoformat(),
                    'last_accessed': datetime.now().isoformat(),
                    'indexed_at': datetime.now().isoformat(),
                    'embedding_model': embedding_model,
                    'collection_name': os.environ.get('RAGEX_CHROMA_COLLECTION', 'code_embeddings')
                }
                save_project_metadata(project_id, metadata)
            
            if not quiet:
                logger.info(f"📦 Project: {project_name}")
                logger.info(f"🤖 Embedding model: {embedding_model}")
            
            # Initialize pattern matcher for ignore handling
            pattern_matcher = PatternMatcher()
            pattern_matcher.set_working_directory(path)
            
            # Check if index exists
            index_exists = (Path(project_data_dir) / 'chroma_db').exists()
            
            # Initialize indexer with project data directory and embedding model
            chroma_persist_dir = get_chroma_db_path(project_data_dir)
            indexer = CodeIndexer(
                persist_directory=str(chroma_persist_dir),
                config=embedding_model
            )
            
            if not index_exists or force:
                # Check for model change confirmation if forcing with different model
                if force and existing_metadata:
                    existing_model = existing_metadata.get('embedding_model', 'fast')
                    # Use same logic as above - resolve actual model being used
                    actual_model_for_force = model or os.environ.get('RAGEX_EMBEDDING_MODEL', 'fast')
                    if actual_model_for_force != existing_model:
                        if not quiet:
                            # Import here to avoid circular dependency
                            from .embedding_config import EmbeddingConfig
                            try:
                                existing_config = EmbeddingConfig(preset=existing_model)
                                new_config = EmbeddingConfig(preset=actual_model_for_force)
                                
                                logger.warning(f"⚠️  WARNING: Changing embedding model with --force")
                                logger.warning(f"   From: '{existing_model}' ({existing_config.dimensions} dimensions)")
                                logger.warning(f"   To:   '{actual_model_for_force}' ({new_config.dimensions} dimensions)")
                                logger.warning(f"   ")
                                logger.warning(f"   This will DELETE all existing embeddings and rebuild from scratch.")
                                logger.warning(f"   Your search history and cached results will be lost.")
                                logger.warning(f"   ")
                                
                                # In a non-interactive environment, we can't prompt
                                # So we just log the warning and proceed
                                logger.warning(f"   Proceeding with forced rebuild...")
                                
                            except Exception:
                                logger.warning(f"⚠️  WARNING: Forcing rebuild with model change from '{existing_model}' to '{actual_model_for_force}'")
                
                # First time or forced - run full index
                if not quiet:
                    reason = "forced rebuild" if force else "no existing index"
                    logger.info(f"📊 Creating full index ({reason})")
                
                # Get all files to index using the indexer's file discovery
                file_paths = indexer.find_code_files([path])
                
                if not file_paths:
                    if not quiet:
                        logger.warning("⚠️  No source files found to index")
                    return {
                        'success': True,
                        'files_processed': 0,
                        'symbols_indexed': 0
                    }
                
                if not quiet:
                    logger.info(f"📊 Indexing {len(file_paths)} files...")
                
                # Index all files
                result = await indexer.index_codebase([str(f) for f in file_paths], force=True)
                
                # Update metadata
                update_metadata = {
                    'files_indexed': result.get('files_processed', 0),
                    'index_completed_at': datetime.now().isoformat(),
                    'full_index': True
                }
                update_project_metadata(project_id, update_metadata)
                
                return result
            else:
                # Incremental update - use existing logic but simplified
                if not quiet:
                    logger.info("🔍 Checking for changes...")
                
                # For now, just do a simple file count check
                # In the future, this could be enhanced with proper incremental logic
                file_paths = indexer.find_code_files([path])
                if file_paths:
                    result = await indexer.index_codebase([str(f) for f in file_paths], force=False)
                    
                    # Update metadata
                    update_metadata = {
                        'files_indexed': result.get('files_processed', 0),
                        'index_completed_at': datetime.now().isoformat(),
                        'incremental_update': True
                    }
                    update_project_metadata(project_id, update_metadata)
                    
                    return result
                else:
                    return {
                        'success': True,
                        'files_processed': 0,
                        'symbols_indexed': 0
                    }
        
        except Exception as e:
            logger.error(f"Enhanced indexing failed: {e}", exc_info=verbose)
            return {
                'success': False,
                'error': str(e)
            }

    async def shutdown(self):
        """Shutdown the queue, cancelling pending operations gracefully"""
        logger.info("Shutting down indexing queue...")
        self._shutdown_requested = True
        
        # Cancel pending timer
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
            try:
                await self._timer_task
            except asyncio.CancelledError:
                pass
        
        # Wait for current indexing to complete (with timeout)
        if self._current_indexing_task and not self._current_indexing_task.done():
            logger.info("Waiting for current indexing to complete...")
            try:
                await asyncio.wait_for(self._current_indexing_task, timeout=30.0)
                logger.info("Indexing completed gracefully")
            except asyncio.TimeoutError:
                logger.warning("Indexing timeout, forcing cancellation")
                self._current_indexing_task.cancel()
                try:
                    await self._current_indexing_task
                except asyncio.CancelledError:
                    pass
