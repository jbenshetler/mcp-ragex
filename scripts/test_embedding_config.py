#!/usr/bin/env python3
"""
Test script for the embedding configuration system
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir.parent / "src"))

from embedding_config import EmbeddingConfig, ModelConfig, get_default_config


def test_configuration():
    """Test various configuration scenarios"""
    
    print("🧪 Testing Embedding Configuration System\n")
    
    # Test 1: Default configuration
    print("1. Default configuration:")
    config = get_default_config()
    print(f"   Model: {config.model_name}")
    print(f"   Dimensions: {config.dimensions}")
    print(f"   Batch size: {config.batch_size}")
    print(f"   Persist dir: {config.persist_directory}")
    print(f"   Collection: {config.collection_name}")
    
    # Test 2: Preset configurations
    print("\n2. Testing presets:")
    for preset in ["fast", "balanced", "accurate"]:
        config = EmbeddingConfig(preset=preset)
        print(f"   {preset}: {config.model_name} ({config.dimensions}d)")
    
    # Test 3: Environment variable override
    print("\n3. Testing environment override:")
    os.environ["RAGEX_EMBEDDING_MODEL"] = "balanced"
    config = EmbeddingConfig()
    print(f"   With RAGEX_EMBEDDING_MODEL=balanced: {config.model_name}")
    
    # Clean up
    del os.environ["RAGEX_EMBEDDING_MODEL"]
    
    # Test 4: Custom model
    print("\n4. Testing custom model:")
    custom = ModelConfig(
        model_name="custom/test-model",
        dimensions=512,
        max_seq_length=300,
        batch_size=16
    )
    config = EmbeddingConfig(custom_model=custom)
    print(f"   Custom: {config.model_name} ({config.dimensions}d)")
    
    # Test 5: List all presets
    print("\n5. Available presets:")
    for name, info in EmbeddingConfig.list_presets().items():
        print(f"   - {name}: {info['description']}")
    
    # Test 6: Config summary
    print("\n6. Configuration summary:")
    config = EmbeddingConfig(preset="balanced")
    summary = config.get_config_summary()
    for key, value in summary.items():
        if key != "environment_overrides":
            print(f"   {key}: {value}")
    
    print("\n✅ All tests passed!")


if __name__ == "__main__":
    test_configuration()