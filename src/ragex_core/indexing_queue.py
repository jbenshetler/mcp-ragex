#!/usr/bin/env python3
"""
Indexing queue for batching file changes.

Collects file change events and triggers re-indexing after a debounce period.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Set, Optional, Callable, List, Dict
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
                 on_index_callback: Optional[Callable[[List[Path], List[Path], Dict[Path, str]], asyncio.Future]] = None):
        """
        Initialize the indexing queue.
        
        Args:
            debounce_seconds: Time to wait after last change before indexing
            on_index_callback: Async callback to trigger indexing (added_files, removed_files, file_checksums)
        """
        self.debounce_seconds = debounce_seconds
        self.on_index_callback = on_index_callback
        
        # File tracking with checksums
        self._added_files: Set[Path] = set()
        self._removed_files: Set[Path] = set()
        self._file_checksums: Dict[Path, str] = {}  # NEW: Store checksums for added files
        self._last_change_time: float = 0
        
        # State
        self._timer_task: Optional[asyncio.Task] = None
        self._indexing: bool = False
        self._lock = asyncio.Lock()
        
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
            # Check if we have changes
            if not self._added_files and not self._removed_files:
                return
            
            # Check if already indexing
            if self._indexing:
                logger.warning("Indexing already in progress, skipping")
                return
            
            # Get files to process
            added_files = list(self._added_files)
            removed_files = list(self._removed_files)
            
            # Clear queues
            self._added_files.clear()
            self._removed_files.clear()
            
            # Mark as indexing
            self._indexing = True
        
        try:
            # Log what we're doing
            if added_files and removed_files:
                logger.info(f"🔄 Re-indexing {len(added_files)} changed files, removing {len(removed_files)} deleted files...")
            elif added_files:
                logger.info(f"🔄 Re-indexing {len(added_files)} changed files...")
            else:
                logger.info(f"🔄 Removing {len(removed_files)} deleted files from index...")
            
            start_time = time.time()
            
            # Calculate checksums for added files
            file_checksums = {}
            if added_files:
                for file_path in added_files:
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
            
        except Exception as e:
            logger.error(f"Failed to re-index files: {e}", exc_info=True)
        finally:
            async with self._lock:
                self._indexing = False
    
    def get_status(self) -> dict:
        """Get current queue status."""
        return {
            'pending_additions': len(self._added_files),
            'pending_removals': len(self._removed_files),
            'is_indexing': self._indexing,
            'last_change': datetime.fromtimestamp(self._last_change_time).isoformat() if self._last_change_time > 0 else None,
            'debounce_seconds': self.debounce_seconds
        }
    
    async def shutdown(self):
        """Shutdown the queue, cancelling any pending timers."""
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
            try:
                await self._timer_task
            except asyncio.CancelledError:
                pass