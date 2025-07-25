#!/usr/bin/env python3
"""
Integration test for watchdog hot reloading with MCP server
"""

import os
import sys
import time
import tempfile
from pathlib import Path
import subprocess
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ignore import IgnoreManager
from src.watchdog_monitor import WatchdogMonitor, WATCHDOG_AVAILABLE


def test_hot_reload():
    """Test that changes to .mcpignore are hot reloaded"""
    print("Testing watchdog hot reload functionality...")
    
    if not WATCHDOG_AVAILABLE:
        print("❌ Watchdog not available - skipping test")
        return False
        
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create initial .mcpignore
        mcpignore = temp_path / ".mcpignore"
        mcpignore.write_text("*.tmp\n")
        
        # Create test files
        (temp_path / "test.py").write_text("# Python file")
        (temp_path / "test.tmp").write_text("# Temp file")
        (temp_path / "data.txt").write_text("# Text file")
        
        # Initialize ignore manager and monitor
        ignore_manager = IgnoreManager(temp_path)
        monitor = WatchdogMonitor(ignore_manager, debounce_seconds=0.5)
        
        changes_detected = []
        
        def on_change(file_path):
            changes_detected.append(file_path)
            print(f"  ✓ Detected change: {file_path}")
            
        # Start monitoring
        monitor.start(on_change_callback=on_change)
        time.sleep(0.5)  # Let monitor start
        
        # Initial state check
        assert ignore_manager.should_ignore("test.tmp"), "test.tmp should be ignored initially"
        assert not ignore_manager.should_ignore("test.py"), "test.py should not be ignored"
        assert not ignore_manager.should_ignore("data.txt"), "data.txt should not be ignored initially"
        
        print("  ✓ Initial state correct")
        
        # Modify .mcpignore
        print("  Modifying .mcpignore...")
        mcpignore.write_text("*.tmp\n*.txt\n")
        
        # Wait for change detection and reload
        time.sleep(1.0)
        
        # Check changes were detected
        assert len(changes_detected) == 1, f"Expected 1 change, got {len(changes_detected)}"
        assert changes_detected[0] == str(mcpignore), "Wrong file detected"
        
        # Check new rules are applied
        assert ignore_manager.should_ignore("test.tmp"), "test.tmp should still be ignored"
        assert not ignore_manager.should_ignore("test.py"), "test.py should still not be ignored"
        assert ignore_manager.should_ignore("data.txt"), "data.txt should now be ignored"
        
        print("  ✓ Hot reload successful")
        
        # Test adding new .mcpignore in subdirectory
        subdir = temp_path / "subdir"
        subdir.mkdir()
        sub_mcpignore = subdir / ".mcpignore"
        
        (subdir / "test.py").write_text("# Python file in subdir")
        (subdir / "test.tmp").write_text("# Temp file in subdir")
        
        print("  Creating subdirectory .mcpignore...")
        sub_mcpignore.write_text("!*.tmp\n")  # Override parent rule
        
        time.sleep(1.0)
        
        # Check multi-level rules
        assert not ignore_manager.should_ignore("subdir/test.tmp"), "Subdirectory override should work"
        assert ignore_manager.should_ignore("test.tmp"), "Parent rule should still apply"
        
        print("  ✓ Multi-level hot reload successful")
        
        # Stop monitor
        monitor.stop()
        
        return True


def test_server_integration():
    """Test watchdog integration with MCP server"""
    print("\nTesting MCP server watchdog integration...")
    
    # Set environment variable
    env = os.environ.copy()
    env["RAGEX_ENABLE_WATCHDOG"] = "true"
    env["MCP_WORKING_DIR"] = os.getcwd()
    
    # Create test request for watchdog status
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "get_watchdog_status",
            "arguments": {}
        }
    }
    
    # Run server and send request
    try:
        proc = subprocess.Popen(
            [sys.executable, "src/server.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True
        )
        
        # Send initialization
        init_request = {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {
                "protocolVersion": "0.1.0",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0.1.0"}
            }
        }
        
        proc.stdin.write(json.dumps(init_request) + "\n")
        proc.stdin.flush()
        
        # Read initialization response
        response_line = proc.stdout.readline()
        if response_line:
            print(f"  ✓ Server initialized")
        
        # Send watchdog status request
        proc.stdin.write(json.dumps(request) + "\n")
        proc.stdin.flush()
        
        # Read response
        response_line = proc.stdout.readline()
        if response_line:
            response = json.loads(response_line)
            if "result" in response:
                content = response["result"][0]["text"]
                if "Watchdog active" in content:
                    print("  ✓ Watchdog is active in server")
                    return True
                elif "Watchdog disabled" in content:
                    print("  ⚠️  Watchdog is disabled (check RAGEX_ENABLE_WATCHDOG)")
                else:
                    print(f"  ❌ Unexpected status: {content[:100]}...")
        
        # Cleanup
        proc.terminate()
        proc.wait(timeout=5)
        
    except Exception as e:
        print(f"  ❌ Error testing server: {e}")
        return False
        
    return False


def main():
    """Run integration tests"""
    print("=" * 50)
    print("Watchdog Integration Tests")
    print("=" * 50)
    
    success = True
    
    # Test hot reload functionality
    if not test_hot_reload():
        success = False
        
    # Test server integration
    if not test_server_integration():
        success = False
        
    print("\n" + "=" * 50)
    if success:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed")
        
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())