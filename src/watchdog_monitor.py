#!/usr/bin/env python3
"""
Watchdog monitor for .gitignore files

This module provides file system monitoring capabilities for the enhanced
ignore system, enabling hot reloading when .gitignore files change.
"""

import logging
from pathlib import Path
from typing import Optional, Set, Callable, Dict, Any
import time
from threading import Thread, Event

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = object
    FileSystemEvent = object

from src.ragex_core.ignore import IgnoreManager, IGNORE_FILENAME

logger = logging.getLogger("watchdog-monitor")


class IgnoreFileHandler(FileSystemEventHandler):
    """
    Watches for changes to .gitignore files and notifies the IgnoreManager
    """
    
    def __init__(self, ignore_manager: IgnoreManager, 
                 debounce_seconds: float = 0.5,
                 on_change_callback: Optional[Callable[[str], None]] = None):
        """
        Initialize the ignore file handler
        
        Args:
            ignore_manager: The IgnoreManager instance to notify
            debounce_seconds: Minimum time between notifications for same file
            on_change_callback: Optional callback when files change
        """
        super().__init__()
        self.ignore_manager = ignore_manager
        self.ignore_filename = ignore_manager.ignore_filename
        self.debounce_seconds = debounce_seconds
        self.on_change_callback = on_change_callback
        self._last_change_times: Dict[str, float] = {}
        
    def _should_process_event(self, event: FileSystemEvent) -> bool:
        """Check if we should process this event"""
        if event.is_directory:
            return False
            
        path = Path(event.src_path)
        
        # Check if it's an ignore file
        if path.name != self.ignore_filename:
            return False
            
        # Debounce rapid changes
        current_time = time.time()
        last_change = self._last_change_times.get(str(path), 0)
        
        if current_time - last_change < self.debounce_seconds:
            logger.debug(f"Debouncing change to {path}")
            return False
            
        self._last_change_times[str(path)] = current_time
        return True
        
    def on_created(self, event: FileSystemEvent):
        """Handle creation of new .gitignore files"""
        if self._should_process_event(event):
            logger.info(f"Detected new {self.ignore_filename}: {event.src_path}")
            self.ignore_manager.notify_file_changed(event.src_path)
            
            if self.on_change_callback:
                self.on_change_callback(event.src_path)
                
    def on_modified(self, event: FileSystemEvent):
        """Handle modification of .gitignore files"""
        if self._should_process_event(event):
            logger.info(f"Detected change to {self.ignore_filename}: {event.src_path}")
            self.ignore_manager.notify_file_changed(event.src_path)
            
            if self.on_change_callback:
                self.on_change_callback(event.src_path)
                
    def on_deleted(self, event: FileSystemEvent):
        """Handle deletion of .gitignore files"""
        if self._should_process_event(event):
            logger.info(f"Detected deletion of {self.ignore_filename}: {event.src_path}")
            self.ignore_manager.notify_file_changed(event.src_path)
            
            if self.on_change_callback:
                self.on_change_callback(event.src_path)
                
    def on_moved(self, event: FileSystemEvent):
        """Handle moving of .gitignore files"""
        if hasattr(event, 'dest_path'):
            # Check both source and destination
            src_is_ignore = Path(event.src_path).name == self.ignore_filename
            dest_is_ignore = Path(event.dest_path).name == self.ignore_filename
            
            if src_is_ignore:
                logger.info(f"Detected move of {self.ignore_filename}: {event.src_path} -> {event.dest_path}")
                self.ignore_manager.notify_file_changed(event.src_path)
                
                if self.on_change_callback:
                    self.on_change_callback(event.src_path)
                    
            if dest_is_ignore and event.dest_path != event.src_path:
                self.ignore_manager.notify_file_changed(event.dest_path)
                
                if self.on_change_callback:
                    self.on_change_callback(event.dest_path)


class WatchdogMonitor:
    """
    Main watchdog monitor that manages file system watching
    """
    
    def __init__(self, ignore_manager: IgnoreManager,
                 recursive: bool = True,
                 debounce_seconds: float = 0.5):
        """
        Initialize the watchdog monitor
        
        Args:
            ignore_manager: The IgnoreManager to integrate with
            recursive: Whether to watch subdirectories
            debounce_seconds: Minimum time between notifications
        """
        if not WATCHDOG_AVAILABLE:
            raise ImportError(
                "watchdog package not installed. "
                "Install with: pip install watchdog"
            )
            
        self.ignore_manager = ignore_manager
        self.recursive = recursive
        self.debounce_seconds = debounce_seconds
        
        self._observer: Optional[Observer] = None
        self._handler: Optional[IgnoreFileHandler] = None
        self._watched_paths: Set[Path] = set()
        self._stop_event = Event()
        
    def start(self, paths: Optional[list[str]] = None,
              on_change_callback: Optional[Callable[[str], None]] = None):
        """
        Start monitoring for changes
        
        Args:
            paths: List of paths to watch (defaults to IgnoreManager root)
            on_change_callback: Optional callback for changes
        """
        if self._observer is not None:
            logger.warning("Monitor already running")
            return
            
        # Use provided paths or default to IgnoreManager root
        if paths is None:
            paths = [str(self.ignore_manager.root_path)]
            
        # Create handler and observer
        self._handler = IgnoreFileHandler(
            self.ignore_manager,
            debounce_seconds=self.debounce_seconds,
            on_change_callback=on_change_callback
        )
        self._observer = Observer()
        
        # Schedule paths
        for path in paths:
            path_obj = Path(path).resolve()
            if path_obj.exists() and path_obj.is_dir():
                self._observer.schedule(
                    self._handler,
                    str(path_obj),
                    recursive=self.recursive
                )
                self._watched_paths.add(path_obj)
                logger.info(f"Watching directory: {path_obj}")
            else:
                logger.warning(f"Path does not exist or is not a directory: {path}")
                
        # Start observer
        self._observer.start()
        logger.info("Watchdog monitor started")
        
    def stop(self):
        """Stop monitoring for changes"""
        if self._observer is None:
            logger.warning("Monitor not running")
            return
            
        self._observer.stop()
        self._observer.join()
        self._observer = None
        self._handler = None
        self._watched_paths.clear()
        
        logger.info("Watchdog monitor stopped")
        
    def is_running(self) -> bool:
        """Check if monitor is running"""
        return self._observer is not None and self._observer.is_alive()
        
    def add_path(self, path: str):
        """Add a path to watch"""
        if self._observer is None:
            raise RuntimeError("Monitor not running")
            
        path_obj = Path(path).resolve()
        if path_obj in self._watched_paths:
            logger.debug(f"Path already watched: {path_obj}")
            return
            
        if path_obj.exists() and path_obj.is_dir():
            self._observer.schedule(
                self._handler,
                str(path_obj),
                recursive=self.recursive
            )
            self._watched_paths.add(path_obj)
            logger.info(f"Added watch path: {path_obj}")
        else:
            logger.warning(f"Cannot add path (not a directory): {path}")
            
    def remove_path(self, path: str):
        """Remove a path from watching"""
        if self._observer is None:
            raise RuntimeError("Monitor not running")
            
        path_obj = Path(path).resolve()
        if path_obj not in self._watched_paths:
            logger.debug(f"Path not watched: {path_obj}")
            return
            
        # Note: watchdog doesn't provide direct unschedule, 
        # would need to stop and restart without this path
        logger.warning(f"Path removal not implemented: {path_obj}")
        
    def get_watched_paths(self) -> list[str]:
        """Get list of currently watched paths"""
        return [str(p) for p in self._watched_paths]
        
    def __enter__(self):
        """Context manager support"""
        self.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup"""
        self.stop()


class ThreadedWatchdogMonitor(WatchdogMonitor):
    """
    Watchdog monitor that runs in a separate thread
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._thread: Optional[Thread] = None
        
    def start_threaded(self, *args, **kwargs):
        """Start monitor in a separate thread"""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("Monitor thread already running")
            return
            
        self._stop_event.clear()
        
        def run():
            self.start(*args, **kwargs)
            # Keep thread alive until stop event
            while not self._stop_event.is_set():
                self._stop_event.wait(1)
            self.stop()
            
        self._thread = Thread(target=run, daemon=True)
        self._thread.start()
        logger.info("Monitor thread started")
        
    def stop_threaded(self):
        """Stop the monitor thread"""
        if self._thread is None:
            return
            
        self._stop_event.set()
        self._thread.join(timeout=5)
        
        if self._thread.is_alive():
            logger.warning("Monitor thread did not stop cleanly")
        else:
            logger.info("Monitor thread stopped")
            
        self._thread = None


def create_ignore_aware_handler(ignore_manager: IgnoreManager) -> FileSystemEventHandler:
    """
    Create a file system event handler that respects ignore rules
    
    This is a convenience function for creating handlers that filter
    events based on ignore rules before processing them.
    
    Args:
        ignore_manager: The IgnoreManager to use for filtering
        
    Returns:
        A FileSystemEventHandler subclass that filters ignored files
    """
    class IgnoreAwareHandler(FileSystemEventHandler):
        def __init__(self):
            self.ignore_manager = ignore_manager
            
        def _should_process(self, event: FileSystemEvent) -> bool:
            """Check if event should be processed"""
            # Always process changes to ignore files themselves
            if Path(event.src_path).name == self.ignore_manager.ignore_filename:
                return True
                
            # Check ignore rules
            return not self.ignore_manager.should_ignore(event.src_path)
            
        def on_any_event(self, event: FileSystemEvent):
            """Filter all events through ignore rules"""
            if not self._should_process(event):
                logger.debug(f"Ignoring event for: {event.src_path}")
                return
                
            # Call parent implementation
            super().on_any_event(event)
            
    return IgnoreAwareHandler


# Example usage
if __name__ == "__main__":
    import sys
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if not WATCHDOG_AVAILABLE:
        print("watchdog package not installed")
        sys.exit(1)
        
    # Create ignore manager
    root_path = Path.cwd()
    ignore_manager = IgnoreManager(root_path)
    
    # Create and start monitor
    monitor = WatchdogMonitor(ignore_manager)
    
    def on_change(file_path: str):
        print(f"✓ Ignore file changed: {file_path}")
        print(f"  Active ignore files: {len(ignore_manager.get_ignore_files())}")
        
    try:
        monitor.start(on_change_callback=on_change)
        print(f"Monitoring {root_path} for changes to {IGNORE_FILENAME} files...")
        print("Press Ctrl+C to stop")
        
        # Keep running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping monitor...")
        monitor.stop()
