#!/usr/bin/env python3
"""
File handler for watchdog that triggers incremental indexing.

Monitors source code files and queues them for re-indexing when changed.
"""

import logging
import asyncio
from pathlib import Path
from typing import Set, Optional

try:
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    FileSystemEventHandler = object
    FileSystemEvent = object

logger = logging.getLogger("indexing-file-handler")


# File extensions to watch for code changes
CODE_EXTENSIONS = {
    '.py', '.js', '.jsx', '.ts', '.tsx', '.go', '.rs', '.java', '.cpp', '.c',
    '.h', '.hpp', '.cs', '.rb', '.php', '.swift', '.kt', '.scala', '.r',
    '.jl', '.lua', '.dart', '.ex', '.exs', '.clj', '.cljs', '.ml', '.fs'
}


class IndexingFileHandler(FileSystemEventHandler):
    """
    Watches for changes to source code files and queues them for re-indexing.
    """
    
    def __init__(self, ignore_manager, indexing_queue):
        """
        Initialize the file handler.
        
        Args:
            ignore_manager: IgnoreManager to check if files should be processed
            indexing_queue: IndexingQueue to add changed files to
        """
        super().__init__()
        self.ignore_manager = ignore_manager
        self.indexing_queue = indexing_queue
        self._loop = None  # Will be set later when events occur
        logger.info("IndexingFileHandler initialized")
        
    def _should_process(self, event: FileSystemEvent) -> bool:
        """Check if we should process this file event."""
        # Skip directories
        if event.is_directory:
            return False
        
        path = Path(event.src_path)
        
        # Check file extension
        if path.suffix.lower() not in CODE_EXTENSIONS:
            return False
        
        # Check ignore rules
        if self.ignore_manager.should_ignore(str(path)):
            logger.debug(f"Ignoring change to: {path} (matched .gitignore pattern)")
            return False
        
        return True
    
    def _get_event_loop(self):
        """Get or create event loop for the current thread."""
        if self._loop is None:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                # No event loop in current thread, try to get the main thread's loop
                import threading
                main_thread = threading.main_thread()
                if hasattr(main_thread, '_loop'):
                    self._loop = main_thread._loop
                else:
                    # Create a new event loop for this thread
                    self._loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(self._loop)
        return self._loop
    
    def _queue_add(self, file_path: str):
        """Queue a file for addition/update with checksum (thread-safe)."""
        logger.info(f"File change detected: {file_path}")
        # Calculate checksum for the changed file
        try:
            from src.ragex_core.file_checksum import calculate_file_checksum
            checksum = calculate_file_checksum(Path(file_path))
            
            loop = self._get_event_loop()
            asyncio.run_coroutine_threadsafe(
                self.indexing_queue.add_file(file_path, checksum),
                loop
            )
            logger.info(f"Queued for indexing: {file_path}")
        except Exception as e:
            # Log error and skip this file - don't queue without checksum
            logger.error(f"Failed to calculate checksum for {file_path}, skipping: {e}")
            # File will be picked up by periodic rescan later
    
    def _queue_remove(self, file_path: str):
        """Queue a file for removal (thread-safe)."""
        logger.info(f"File deletion detected: {file_path}")
        loop = self._get_event_loop()
        asyncio.run_coroutine_threadsafe(
            self.indexing_queue.remove_file(file_path),
            loop
        )
        logger.info(f"Queued for removal: {file_path}")
    
    def on_created(self, event: FileSystemEvent):
        """Handle file creation."""
        if self._should_process(event):
            self._queue_add(event.src_path)
    
    def on_modified(self, event: FileSystemEvent):
        """Handle file modification."""
        if self._should_process(event):
            self._queue_add(event.src_path)
    
    def on_deleted(self, event: FileSystemEvent):
        """Handle file deletion."""
        if self._should_process(event):
            self._queue_remove(event.src_path)
    
    def on_moved(self, event: FileSystemEvent):
        """Handle file move/rename."""
        # Check source
        if hasattr(event, 'src_path'):
            src_path = Path(event.src_path)
            if src_path.suffix.lower() in CODE_EXTENSIONS:
                # Source was a code file, mark for removal
                if not self.ignore_manager.should_ignore(str(src_path)):
                    self._queue_remove(event.src_path)
        
        # Check destination
        if hasattr(event, 'dest_path'):
            dest_path = Path(event.dest_path)
            if dest_path.suffix.lower() in CODE_EXTENSIONS:
                # Destination is a code file, mark for addition
                if not self.ignore_manager.should_ignore(str(dest_path)):
                    self._queue_add(event.dest_path)
