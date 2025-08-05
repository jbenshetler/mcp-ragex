#!/usr/bin/env python3
"""
Basic tests to ensure CI/CD pipeline passes
"""

import json
import os
import sys
from pathlib import Path


def test_version_import():
    """Test that we can import and check version"""
    # Add src to path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    # Import ragex CLI
    from ragex import RagexCLI, __version__
    
    # Basic checks
    assert __version__ == "2.0.0"
    
    # Can create CLI instance
    cli = RagexCLI()
    assert cli is not None
    assert hasattr(cli, 'docker_image')
    assert hasattr(cli, 'user_id')


def test_config_functionality():
    """Test configuration loading/saving"""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from ragex import RagexCLI
    
    cli = RagexCLI()
    
    # Test config directory creation
    config_dir = cli.get_config_dir()
    assert config_dir is not None
    assert "ragex" in str(config_dir)
    
    # Test empty config loading
    config = cli.load_config()
    assert isinstance(config, dict)


def test_gpu_detection_methods():
    """Test GPU detection methods don't crash"""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from ragex import RagexCLI
    
    cli = RagexCLI()
    
    # These should not crash (even if GPU not available)
    is_cuda = cli.is_cuda_image()
    assert isinstance(is_cuda, bool)
    
    gpu_available = cli.is_gpu_available()
    assert isinstance(gpu_available, bool)
    
    should_use = cli.should_use_gpu()
    assert isinstance(should_use, bool)


def test_project_id_generation():
    """Test project ID generation"""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from ragex import RagexCLI
    
    cli = RagexCLI()
    
    # Test project ID generation
    test_path = Path("/tmp/test")
    project_id = cli.generate_project_id(test_path)
    
    assert isinstance(project_id, str)
    assert project_id.startswith("ragex_")
    assert str(cli.user_id) in project_id


def test_daemon_container_name():
    """Test daemon container naming"""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from ragex import RagexCLI
    
    cli = RagexCLI()
    
    # Test container name generation
    container_name = cli.daemon_container_name
    assert isinstance(container_name, str)
    assert container_name.startswith("ragex_daemon_")


if __name__ == "__main__":
    # Run tests directly
    test_version_import()
    test_config_functionality()
    test_gpu_detection_methods()
    test_project_id_generation()
    test_daemon_container_name()
    print("✅ All basic tests passed!")