#!/usr/bin/env python3
"""
Test suite for watchdog monitor integration
"""

import unittest
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock watchdog if not installed
try:
    import watchdog
    WATCHDOG_INSTALLED = True
except ImportError:
    WATCHDOG_INSTALLED = False
    sys.modules['watchdog'] = MagicMock()
    sys.modules['watchdog.observers'] = MagicMock()
    sys.modules['watchdog.events'] = MagicMock()

from src.ignore import IgnoreManager
from src.watchdog_monitor import (
    IgnoreFileHandler, WatchdogMonitor, ThreadedWatchdogMonitor,
    create_ignore_aware_handler, WATCHDOG_AVAILABLE
)


class TestIgnoreFileHandler(unittest.TestCase):
    """Test the IgnoreFileHandler class"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_path = Path(self.temp_dir.name)
        self.ignore_manager = IgnoreManager(self.root_path)
        self.handler = IgnoreFileHandler(self.ignore_manager)
        
    def tearDown(self):
        """Clean up"""
        self.temp_dir.cleanup()
        
    def test_handler_initialization(self):
        """Test handler initialization"""
        callback = Mock()
        handler = IgnoreFileHandler(
            self.ignore_manager,
            debounce_seconds=1.0,
            on_change_callback=callback
        )
        
        self.assertEqual(handler.ignore_manager, self.ignore_manager)
        self.assertEqual(handler.ignore_filename, ".mcpignore")
        self.assertEqual(handler.debounce_seconds, 1.0)
        self.assertEqual(handler.on_change_callback, callback)
        
    def test_should_process_event(self):
        """Test event filtering logic"""
        # Mock events
        class MockEvent:
            def __init__(self, path, is_directory=False):
                self.src_path = path
                self.is_directory = is_directory
                
        # Directory event - should not process
        event = MockEvent("/path/to/dir", is_directory=True)
        self.assertFalse(self.handler._should_process_event(event))
        
        # Non-ignore file - should not process
        event = MockEvent("/path/to/file.py")
        self.assertFalse(self.handler._should_process_event(event))
        
        # Ignore file - should process
        event = MockEvent("/path/to/.mcpignore")
        self.assertTrue(self.handler._should_process_event(event))
        
    def test_debouncing(self):
        """Test that rapid changes are debounced"""
        class MockEvent:
            def __init__(self, path):
                self.src_path = path
                self.is_directory = False
                
        event = MockEvent("/path/to/.mcpignore")
        
        # First event should process
        self.assertTrue(self.handler._should_process_event(event))
        
        # Immediate second event should be debounced
        self.assertFalse(self.handler._should_process_event(event))
        
        # Wait for debounce period
        time.sleep(self.handler.debounce_seconds + 0.1)
        
        # Now should process again
        self.assertTrue(self.handler._should_process_event(event))
        
    @patch.object(IgnoreManager, 'notify_file_changed')
    def test_on_created(self, mock_notify):
        """Test handling of file creation"""
        class MockEvent:
            src_path = "/path/to/.mcpignore"
            is_directory = False
            
        callback = Mock()
        self.handler.on_change_callback = callback
        
        self.handler.on_created(MockEvent())
        
        mock_notify.assert_called_once_with("/path/to/.mcpignore")
        callback.assert_called_once_with("/path/to/.mcpignore")
        
    @patch.object(IgnoreManager, 'notify_file_changed')
    def test_on_modified(self, mock_notify):
        """Test handling of file modification"""
        class MockEvent:
            src_path = "/path/to/.mcpignore"
            is_directory = False
            
        self.handler.on_modified(MockEvent())
        mock_notify.assert_called_once()
        
    @patch.object(IgnoreManager, 'notify_file_changed')
    def test_on_deleted(self, mock_notify):
        """Test handling of file deletion"""
        class MockEvent:
            src_path = "/path/to/.mcpignore"
            is_directory = False
            
        self.handler.on_deleted(MockEvent())
        mock_notify.assert_called_once()
        
    @patch.object(IgnoreManager, 'notify_file_changed')
    def test_on_moved(self, mock_notify):
        """Test handling of file moves"""
        class MockEvent:
            src_path = "/path/to/.mcpignore"
            dest_path = "/path/to/subdir/.mcpignore"
            is_directory = False
            
        self.handler.on_moved(MockEvent())
        
        # Should notify for both source and destination
        self.assertEqual(mock_notify.call_count, 2)


@unittest.skipUnless(WATCHDOG_INSTALLED, "watchdog not installed")
class TestWatchdogMonitor(unittest.TestCase):
    """Test the WatchdogMonitor class"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_path = Path(self.temp_dir.name)
        self.ignore_manager = IgnoreManager(self.root_path)
        self.monitor = WatchdogMonitor(self.ignore_manager)
        
    def tearDown(self):
        """Clean up"""
        if self.monitor.is_running():
            self.monitor.stop()
        self.temp_dir.cleanup()
        
    def test_monitor_initialization(self):
        """Test monitor initialization"""
        monitor = WatchdogMonitor(
            self.ignore_manager,
            recursive=False,
            debounce_seconds=2.0
        )
        
        self.assertEqual(monitor.ignore_manager, self.ignore_manager)
        self.assertFalse(monitor.recursive)
        self.assertEqual(monitor.debounce_seconds, 2.0)
        self.assertIsNone(monitor._observer)
        self.assertFalse(monitor.is_running())
        
    def test_start_stop(self):
        """Test starting and stopping monitor"""
        # Should not be running initially
        self.assertFalse(self.monitor.is_running())
        
        # Start monitor
        self.monitor.start()
        self.assertTrue(self.monitor.is_running())
        self.assertIsNotNone(self.monitor._observer)
        
        # Stop monitor
        self.monitor.stop()
        self.assertFalse(self.monitor.is_running())
        self.assertIsNone(self.monitor._observer)
        
    def test_start_with_callback(self):
        """Test starting with callback"""
        callback = Mock()
        self.monitor.start(on_change_callback=callback)
        
        self.assertTrue(self.monitor.is_running())
        self.assertEqual(self.monitor._handler.on_change_callback, callback)
        
    def test_context_manager(self):
        """Test context manager usage"""
        with WatchdogMonitor(self.ignore_manager) as monitor:
            self.assertTrue(monitor.is_running())
            
        self.assertFalse(monitor.is_running())
        
    def test_add_path(self):
        """Test adding paths to watch"""
        # Create subdirectory
        subdir = self.root_path / "subdir"
        subdir.mkdir()
        
        self.monitor.start()
        initial_count = len(self.monitor.get_watched_paths())
        
        # Add new path
        self.monitor.add_path(str(subdir))
        self.assertEqual(len(self.monitor.get_watched_paths()), initial_count + 1)
        self.assertIn(str(subdir), self.monitor.get_watched_paths())
        
    def test_file_change_detection(self):
        """Test actual file change detection"""
        changes_detected = []
        
        def on_change(file_path):
            changes_detected.append(file_path)
            
        # Start monitor
        self.monitor.start(on_change_callback=on_change)
        time.sleep(0.1)  # Let observer start
        
        # Create .mcpignore file
        ignore_file = self.root_path / ".mcpignore"
        ignore_file.write_text("*.tmp\n")
        
        # Wait for change detection
        time.sleep(1.0)
        
        # Should have detected the change
        self.assertEqual(len(changes_detected), 1)
        self.assertEqual(Path(changes_detected[0]).name, ".mcpignore")


class TestThreadedWatchdogMonitor(unittest.TestCase):
    """Test the ThreadedWatchdogMonitor class"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_path = Path(self.temp_dir.name)
        self.ignore_manager = IgnoreManager(self.root_path)
        
    def tearDown(self):
        """Clean up"""
        self.temp_dir.cleanup()
        
    @unittest.skipUnless(WATCHDOG_INSTALLED, "watchdog not installed")
    def test_threaded_start_stop(self):
        """Test threaded monitor start/stop"""
        monitor = ThreadedWatchdogMonitor(self.ignore_manager)
        
        # Start in thread
        monitor.start_threaded()
        time.sleep(0.5)  # Let thread start
        
        self.assertTrue(monitor.is_running())
        
        # Stop thread
        monitor.stop_threaded()
        
        # Should be stopped
        self.assertFalse(monitor.is_running())


class TestIgnoreAwareHandler(unittest.TestCase):
    """Test the ignore-aware handler factory"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_path = Path(self.temp_dir.name)
        self.ignore_manager = IgnoreManager(self.root_path)
        
    def tearDown(self):
        """Clean up"""
        self.temp_dir.cleanup()
        
    def test_create_ignore_aware_handler(self):
        """Test creating ignore-aware handler"""
        Handler = create_ignore_aware_handler(self.ignore_manager)
        handler = Handler()
        
        self.assertEqual(handler.ignore_manager, self.ignore_manager)
        
        # Mock event
        class MockEvent:
            def __init__(self, path):
                self.src_path = path
                
        # .mcpignore files should always process
        event = MockEvent("/path/to/.mcpignore")
        self.assertTrue(handler._should_process(event))
        
        # Create .mcpignore with pattern
        ignore_file = self.root_path / ".mcpignore"
        ignore_file.write_text("*.tmp\n")
        
        # Reload to pick up new patterns
        self.ignore_manager.reload_all()
        
        # Ignored file should not process
        event = MockEvent(str(self.root_path / "test.tmp"))
        self.assertFalse(handler._should_process(event))
        
        # Non-ignored file should process
        event = MockEvent(str(self.root_path / "test.py"))
        self.assertTrue(handler._should_process(event))


class TestWatchdogAvailability(unittest.TestCase):
    """Test behavior when watchdog is not available"""
    
    def test_import_error(self):
        """Test that proper error is raised when watchdog not available"""
        # Temporarily make watchdog unavailable
        with patch('src.watchdog_monitor.WATCHDOG_AVAILABLE', False):
            ignore_manager = Mock()
            
            with self.assertRaises(ImportError) as ctx:
                WatchdogMonitor(ignore_manager)
                
            self.assertIn("watchdog package not installed", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()