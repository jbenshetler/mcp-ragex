#!/usr/bin/env python3
"""
Example of integrating the enhanced ignore system with Python watchdog

This shows how to use the ignore system with external file monitoring
for hot reloading of .mcpignore files.
"""

import logging
import time
from pathlib import Path

# Example with watchdog (install with: pip install watchdog)
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    print("Install watchdog for file monitoring: pip install watchdog")

from src.ignore import IgnoreManager, IGNORE_FILENAME

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class IgnoreFileHandler(FileSystemEventHandler):
    """Watchdog handler that notifies IgnoreManager of changes"""
    
    def __init__(self, ignore_manager: IgnoreManager):
        self.ignore_manager = ignore_manager
        self.ignore_filename = ignore_manager.ignore_filename
        
    def on_modified(self, event):
        if event.is_directory:
            return
            
        # Check if it's an ignore file
        if Path(event.src_path).name == self.ignore_filename:
            print(f"Detected change in: {event.src_path}")
            self.ignore_manager.notify_file_changed(event.src_path)
            
    def on_created(self, event):
        if event.is_directory:
            return
            
        # New ignore file created
        if Path(event.src_path).name == self.ignore_filename:
            print(f"Detected new ignore file: {event.src_path}")
            self.ignore_manager.notify_file_changed(event.src_path)
            
    def on_deleted(self, event):
        if event.is_directory:
            return
            
        # Ignore file deleted
        if Path(event.src_path).name == self.ignore_filename:
            print(f"Detected deletion of: {event.src_path}")
            self.ignore_manager.notify_file_changed(event.src_path)


def main():
    """Example usage of ignore system with watchdog"""
    
    # Initialize ignore manager
    project_root = Path.cwd()
    print(f"Initializing ignore manager for: {project_root}")
    
    ignore_manager = IgnoreManager(project_root)
    
    # Show initial state
    print(f"\nDiscovered {len(ignore_manager.get_ignore_files())} ignore files:")
    for file in ignore_manager.get_ignore_files():
        print(f"  - {file}")
        
    # Test some paths
    test_paths = [
        "test.pyc",
        "src/main.py",
        "__pycache__/module.pyc",
        "important.log",
    ]
    
    print("\nInitial ignore decisions:")
    for path in test_paths:
        ignored = ignore_manager.should_ignore(path)
        print(f"  {path}: {'IGNORED' if ignored else 'included'}")
        
    # Set up file monitoring if watchdog is available
    if WATCHDOG_AVAILABLE:
        print(f"\nStarting file monitor (watching for {IGNORE_FILENAME} changes)...")
        
        # Create observer
        observer = Observer()
        handler = IgnoreFileHandler(ignore_manager)
        
        # Watch the project directory recursively
        observer.schedule(handler, str(project_root), recursive=True)
        observer.start()
        
        try:
            print("Monitoring for changes... (Ctrl+C to stop)")
            print(f"Try modifying any {IGNORE_FILENAME} file to see hot reloading in action!")
            
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            observer.stop()
            print("\nStopping file monitor...")
            
        observer.join()
        
    else:
        print("\nWatchdog not available - demonstrating manual reload:")
        
        # Simulate a file change
        print(f"\nSimulating change to {project_root / IGNORE_FILENAME}")
        ignore_manager.notify_file_changed(project_root / IGNORE_FILENAME)
        
        print("\nIgnore decisions after reload:")
        for path in test_paths:
            ignored = ignore_manager.should_ignore(path)
            print(f"  {path}: {'IGNORED' if ignored else 'included'}")
            
    # Show cache statistics
    stats = ignore_manager.get_stats()
    print("\nCache statistics:")
    print(f"  Path cache: {stats['cache']['path_cache']}")
    print(f"  Registry: {stats['registry']}")


def example_integration_patterns():
    """Show various integration patterns"""
    
    print("\n" + "="*60)
    print("INTEGRATION PATTERNS")
    print("="*60)
    
    # Pattern 1: Basic usage
    print("\n1. Basic Usage:")
    print("```python")
    print("from src.ignore import IgnoreManager")
    print("")
    print("manager = IgnoreManager('/path/to/project')")
    print("if not manager.should_ignore('src/main.py'):")
    print("    process_file('src/main.py')")
    print("```")
    
    # Pattern 2: With custom defaults
    print("\n2. Custom Default Patterns:")
    print("```python")
    print("manager = IgnoreManager(")
    print("    root_path='/path/to/project',")
    print("    default_patterns=['*.tmp', '*.cache', 'logs/']")
    print(")")
    print("```")
    
    # Pattern 3: Manual change notification
    print("\n3. Manual Change Notification:")
    print("```python")
    print("# When you know a file changed")
    print("manager.notify_file_changed('/path/to/.mcpignore')")
    print("```")
    
    # Pattern 4: Integration with file processing
    print("\n4. File Processing Integration:")
    print("```python")
    print("for file_path in Path('.').rglob('*.py'):")
    print("    if not manager.should_ignore(file_path):")
    print("        analyze_python_file(file_path)")
    print("```")
    
    # Pattern 5: Validation and debugging
    print("\n5. Validation and Debugging:")
    print("```python")
    print("# Validate all ignore files")
    print("reports = manager.validate_all()")
    print("for file_path, info in reports.items():")
    print("    if info.errors:")
    print("        print(f'Errors in {file_path}:')")
    print("        for error in info.errors:")
    print("            print(f'  Line {error.line}: {error.message}')")
    print("```")


if __name__ == "__main__":
    main()
    example_integration_patterns()