#!/usr/bin/env python3
"""
Example of using the watchdog monitor with the enhanced ignore system

This example demonstrates:
1. Setting up the watchdog monitor
2. Handling .mcpignore file changes
3. Using ignore-aware file processing
"""

import sys
import time
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ignore import IgnoreManager
from src.watchdog_monitor import WatchdogMonitor, ThreadedWatchdogMonitor, create_ignore_aware_handler

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("watchdog-example")


def example_basic_monitoring():
    """Basic example of monitoring .mcpignore changes"""
    print("\n=== Basic Watchdog Monitoring ===")
    
    # Create ignore manager for current directory
    ignore_manager = IgnoreManager(Path.cwd())
    
    # Create monitor
    monitor = WatchdogMonitor(ignore_manager, debounce_seconds=1.0)
    
    # Define callback for changes
    def on_ignore_change(file_path: str):
        print(f"\n✓ Ignore file changed: {file_path}")
        
        # Show current ignore files
        ignore_files = ignore_manager.get_ignore_files()
        print(f"  Active ignore files: {len(ignore_files)}")
        for f in ignore_files:
            print(f"    - {f}")
            
        # Test a file
        test_file = "test.pyc"
        ignored = ignore_manager.should_ignore(test_file)
        print(f"  Is '{test_file}' ignored? {ignored}")
        
    # Start monitoring
    try:
        monitor.start(on_change_callback=on_ignore_change)
        print(f"Monitoring {Path.cwd()} for .mcpignore changes...")
        print("Try creating or modifying .mcpignore files")
        print("Press Ctrl+C to stop\n")
        
        # Keep running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping monitor...")
    finally:
        monitor.stop()


def example_threaded_monitoring():
    """Example using threaded monitor"""
    print("\n=== Threaded Watchdog Monitoring ===")
    
    # Create ignore manager
    ignore_manager = IgnoreManager(Path.cwd())
    
    # Create threaded monitor
    monitor = ThreadedWatchdogMonitor(ignore_manager)
    
    # Start in background thread
    monitor.start_threaded()
    print(f"Monitor running in background thread")
    print(f"Watching: {monitor.get_watched_paths()}")
    
    # Simulate doing other work
    for i in range(10):
        print(f"Doing work... {i+1}/10")
        time.sleep(1)
        
        # Check if any changes occurred
        if i == 5:
            print("Adding another path to watch...")
            monitor.add_path("src")
            
    # Stop monitor
    monitor.stop_threaded()
    print("Monitor stopped")


def example_ignore_aware_processing():
    """Example of processing files while respecting ignore rules"""
    print("\n=== Ignore-Aware File Processing ===")
    
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEvent
    except ImportError:
        print("watchdog package not installed")
        return
        
    # Create ignore manager
    ignore_manager = IgnoreManager(Path.cwd())
    
    # Create custom handler that respects ignore rules
    IgnoreAwareHandler = create_ignore_aware_handler(ignore_manager)
    
    class FileProcessor(IgnoreAwareHandler):
        def on_created(self, event: FileSystemEvent):
            if not event.is_directory:
                print(f"New file (not ignored): {event.src_path}")
                
        def on_modified(self, event: FileSystemEvent):
            if not event.is_directory:
                print(f"Modified file (not ignored): {event.src_path}")
                
    # Setup observer
    observer = Observer()
    handler = FileProcessor()
    observer.schedule(handler, str(Path.cwd()), recursive=True)
    
    try:
        observer.start()
        print("Watching for file changes (ignoring patterns from .mcpignore)...")
        print("Create or modify files to see which ones are processed")
        print("Press Ctrl+C to stop\n")
        
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping observer...")
    finally:
        observer.stop()
        observer.join()


def example_context_manager():
    """Example using context manager"""
    print("\n=== Context Manager Usage ===")
    
    ignore_manager = IgnoreManager(Path.cwd())
    
    # Use context manager for automatic cleanup
    with WatchdogMonitor(ignore_manager) as monitor:
        print("Monitor started with context manager")
        print("Monitoring for 5 seconds...")
        
        for i in range(5):
            print(f"  {5-i} seconds remaining...")
            time.sleep(1)
            
    print("Monitor automatically stopped")


def main():
    """Run examples"""
    print("Watchdog Integration Examples")
    print("=" * 50)
    
    # Check if watchdog is available
    try:
        import watchdog
        print(f"✓ watchdog {watchdog.__version__} is installed")
    except ImportError:
        print("✗ watchdog is not installed")
        print("  Install with: pip install watchdog")
        return
        
    # Run examples
    examples = [
        ("Basic Monitoring", example_basic_monitoring),
        ("Threaded Monitoring", example_threaded_monitoring),
        ("Ignore-Aware Processing", example_ignore_aware_processing),
        ("Context Manager", example_context_manager),
    ]
    
    for i, (name, func) in enumerate(examples, 1):
        print(f"\n{i}. {name}")
        
    choice = input("\nSelect example (1-4) or 'all' for all examples: ").strip()
    
    if choice.lower() == 'all':
        for name, func in examples:
            func()
            input("\nPress Enter to continue...")
    elif choice.isdigit() and 1 <= int(choice) <= len(examples):
        examples[int(choice)-1][1]()
    else:
        print("Invalid choice")


if __name__ == "__main__":
    main()