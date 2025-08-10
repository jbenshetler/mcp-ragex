#!/usr/bin/env python3
"""
Centralized embedding configuration system for RAGex MCP.

This module provides a unified configuration for embedding models and ChromaDB settings,
supporting environment variable overrides and predefined model presets.
"""

import os
from dataclasses import dataclass
from typing import Dict, Optional
import logging

logger = logging.getLogger("embedding-config")


@dataclass
class ModelConfig:
    """Configuration for a sentence-transformers model"""
    model_name: str
    dimensions: int
    max_seq_length: int
    batch_size: int = 32
    normalize_embeddings: bool = True
    
    def __post_init__(self):
        """Validate configuration"""
        if self.dimensions <= 0:
            raise ValueError(f"dimensions must be positive, got {self.dimensions}")
        if self.max_seq_length <= 0:
            raise ValueError(f"max_seq_length must be positive, got {self.max_seq_length}")
        if self.batch_size <= 0:
            raise ValueError(f"batch_size must be positive, got {self.batch_size}")


@dataclass
class HNSWConfig:
    """Configuration for HNSW index parameters
    
    HNSW (Hierarchical Navigable Small World) is the algorithm used by ChromaDB
    for efficient similarity search. These parameters control the trade-off between
    search speed, index build time, and search quality.
    
    Parameters:
        construction_ef: Size of the dynamic list for the nearest neighbors during construction.
                        Higher values give better accuracy but slower index building.
                        Range: 10-500, default: 100 (optimized for faster indexing)
        
        search_ef: Size of the dynamic list for the nearest neighbors during search.
                  Higher values give better recall but slower search.
                  Range: 10-500, default: 50 (optimized for faster search)
                  Must be >= k (number of results requested)
        
        M: Number of bi-directional links created for each node.
           Higher values give better recall but use more memory and are slower.
           Range: 2-100, default: 16 (balanced for performance)
           
    Performance Guidelines:
        - For faster indexing: Lower construction_ef (50-100)
        - For faster search: Lower search_ef (10-50) and M (8-16)
        - For better quality: Higher values for all parameters
        - Memory usage scales with M
    """
    construction_ef: int = 100  # Optimized for faster indexing
    search_ef: int = 50        # Optimized for faster search
    M: int = 16               # Optimized for memory and speed
    
    def __post_init__(self):
        """Validate HNSW parameters"""
        if not 10 <= self.construction_ef <= 500:
            raise ValueError(f"construction_ef must be between 10 and 500, got {self.construction_ef}")
        if not 10 <= self.search_ef <= 500:
            raise ValueError(f"search_ef must be between 10 and 500, got {self.search_ef}")
        if not 2 <= self.M <= 100:
            raise ValueError(f"M must be between 2 and 100, got {self.M}")


class EmbeddingConfig:
    """Centralized configuration for embeddings and vector storage"""
    
    # Predefined model configurations
    MODEL_PRESETS: Dict[str, ModelConfig] = {
        # Fast model - good for quick prototyping and smaller codebases
        # Pre-bundled in all Docker images for offline operation
        "fast": ModelConfig(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            dimensions=384,
            max_seq_length=256,
            batch_size=64,
            normalize_embeddings=True
        ),
        
        # Balanced model - good balance of speed and quality
        "balanced": ModelConfig(
            model_name="sentence-transformers/all-mpnet-base-v2",
            dimensions=768,
            max_seq_length=384,
            batch_size=32,
            normalize_embeddings=True
        ),
        
        # Accurate model - best quality but slower
        "accurate": ModelConfig(
            model_name="sentence-transformers/all-roberta-large-v1",
            dimensions=1024,
            max_seq_length=512,
            batch_size=16,
            normalize_embeddings=True
        ),
        
        # Multilingual support - works with multiple languages
        "multilingual": ModelConfig(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            dimensions=384,
            max_seq_length=128,
            batch_size=32,
            normalize_embeddings=True
        ),
        
        # Code-specific models (experimental - falls back to fast for now)
        "code-small": ModelConfig(
            model_name="sentence-transformers/all-MiniLM-L6-v2",  # Using fast model as fallback
            dimensions=384,
            max_seq_length=256,
            batch_size=64,
            normalize_embeddings=True
        )
    }
    
    # Default preset
    DEFAULT_PRESET = "fast"
    
    def __init__(self, 
                 preset: Optional[str] = None,
                 custom_model: Optional[ModelConfig] = None,
                 persist_directory: Optional[str] = None,
                 collection_name: Optional[str] = None,
                 hnsw_config: Optional[HNSWConfig] = None):
        """Initialize embedding configuration
        
        Args:
            preset: Name of a predefined model preset ("fast", "balanced", "accurate")
            custom_model: Custom ModelConfig to use instead of preset
            persist_directory: Override for ChromaDB persistence directory
            collection_name: Override for ChromaDB collection name
            hnsw_config: HNSW index configuration for ChromaDB
        """
        # Determine which model config to use
        if custom_model:
            self._model_config = custom_model
            logger.info(f"Using custom model configuration: {custom_model.model_name}")
        else:
            # Check environment variable first
            env_model = os.getenv("RAGEX_EMBEDDING_MODEL")
            if env_model:
                # Check if it's a preset name
                if env_model.lower() in self.MODEL_PRESETS:
                    preset = env_model.lower()
                    logger.info(f"Using preset from environment: {preset}")
                    # Continue to preset resolution below
                else:
                    # Assume it's a model name, create config with defaults
                    self._model_config = ModelConfig(
                        model_name=env_model,
                        dimensions=384,  # Default, will need adjustment based on actual model
                        max_seq_length=256,
                        batch_size=32,
                        normalize_embeddings=True
                    )
                    logger.warning(f"Using custom model from environment: {env_model}")
                    logger.warning("Using default dimensions (384) - adjust if needed")
                    return
            
            # Use preset (either from environment or parameter)
            preset = preset or self.DEFAULT_PRESET
            if preset not in self.MODEL_PRESETS:
                logger.warning(f"Unknown preset '{preset}', using default '{self.DEFAULT_PRESET}'")
                preset = self.DEFAULT_PRESET
            
            self._model_config = self.MODEL_PRESETS[preset]
            logger.info(f"Using preset '{preset}': {self._model_config.model_name}")
        
        # ChromaDB settings with environment overrides
        self._persist_directory = (
            persist_directory or 
            os.getenv("RAGEX_CHROMA_PERSIST_DIR", "./chroma_db")
        )
        self._collection_name = (
            collection_name or 
            os.getenv("RAGEX_CHROMA_COLLECTION", "code_embeddings")
        )
        
        # HNSW configuration with environment overrides
        if hnsw_config:
            self._hnsw_config = hnsw_config
        else:
            # Check for environment overrides
            construction_ef = int(os.getenv("RAGEX_HNSW_CONSTRUCTION_EF", "100"))
            search_ef = int(os.getenv("RAGEX_HNSW_SEARCH_EF", "50"))
            M = int(os.getenv("RAGEX_HNSW_M", "16"))
            
            self._hnsw_config = HNSWConfig(
                construction_ef=construction_ef,
                search_ef=search_ef,
                M=M
            )
        
        logger.info(f"HNSW config: construction_ef={self._hnsw_config.construction_ef}, "
                   f"search_ef={self._hnsw_config.search_ef}, M={self._hnsw_config.M}")
    
    @property
    def model_name(self) -> str:
        """Get the model name"""
        return self._model_config.model_name
    
    @property
    def dimensions(self) -> int:
        """Get the embedding dimensions"""
        return self._model_config.dimensions
    
    @property
    def max_seq_length(self) -> int:
        """Get the maximum sequence length"""
        return self._model_config.max_seq_length
    
    @property
    def batch_size(self) -> int:
        """Get the batch size for encoding"""
        return self._model_config.batch_size
    
    @property
    def normalize_embeddings(self) -> bool:
        """Whether to normalize embeddings"""
        return self._model_config.normalize_embeddings
    
    @property
    def persist_directory(self) -> str:
        """Get the ChromaDB persistence directory"""
        return self._persist_directory
    
    @property
    def collection_name(self) -> str:
        """Get the ChromaDB collection name"""
        return self._collection_name
    
    @property
    def model_config(self) -> ModelConfig:
        """Get the full model configuration"""
        return self._model_config
    
    @property
    def hnsw_config(self) -> HNSWConfig:
        """Get the HNSW configuration"""
        return self._hnsw_config
    
    @property
    def hnsw_construction_ef(self) -> int:
        """Get HNSW construction_ef parameter"""
        return self._hnsw_config.construction_ef
    
    @property
    def hnsw_search_ef(self) -> int:
        """Get HNSW search_ef parameter"""
        return self._hnsw_config.search_ef
    
    @property
    def hnsw_M(self) -> int:
        """Get HNSW M parameter"""
        return self._hnsw_config.M
    
    def get_config_summary(self) -> Dict[str, any]:
        """Get a summary of the configuration"""
        return {
            "model_name": self.model_name,
            "dimensions": self.dimensions,
            "max_seq_length": self.max_seq_length,
            "batch_size": self.batch_size,
            "normalize_embeddings": self.normalize_embeddings,
            "persist_directory": self.persist_directory,
            "collection_name": self.collection_name,
            "hnsw_config": {
                "construction_ef": self.hnsw_construction_ef,
                "search_ef": self.hnsw_search_ef,
                "M": self.hnsw_M
            },
            "environment_overrides": {
                # Container-level environment variables (managed in embedding_config.py)
                "RAGEX_EMBEDDING_MODEL": os.getenv("RAGEX_EMBEDDING_MODEL"),
                "RAGEX_CHROMA_PERSIST_DIR": os.getenv("RAGEX_CHROMA_PERSIST_DIR"),
                "RAGEX_CHROMA_COLLECTION": os.getenv("RAGEX_CHROMA_COLLECTION"),
                "RAGEX_HNSW_CONSTRUCTION_EF": os.getenv("RAGEX_HNSW_CONSTRUCTION_EF"),
                "RAGEX_HNSW_SEARCH_EF": os.getenv("RAGEX_HNSW_SEARCH_EF"),
                "RAGEX_HNSW_M": os.getenv("RAGEX_HNSW_M")
                # NOTE: Host-level CLI variables (like RAGEX_LOG_MAX_SIZE, RAGEX_LOG_MAX_FILES) 
                # are handled directly in the ragex CLI script since they control Docker 
                # container creation, not container-internal behavior.
            }
        }
    
    @classmethod
    def list_presets(cls) -> Dict[str, Dict[str, any]]:
        """List all available presets with their configurations"""
        return {
            name: {
                "model_name": config.model_name,
                "dimensions": config.dimensions,
                "max_seq_length": config.max_seq_length,
                "description": cls._get_preset_description(name)
            }
            for name, config in cls.MODEL_PRESETS.items()
        }
    
    @staticmethod
    def _get_preset_description(preset_name: str) -> str:
        """Get a description for a preset"""
        descriptions = {
            "fast": "Fast model for quick prototyping and smaller codebases",
            "balanced": "Balanced model with good speed and quality trade-off",
            "accurate": "Most accurate model but slower processing",
            "code-small": "Optimized for code understanding (small model)",
            "multilingual": "Support for multiple programming languages and natural languages"
        }
        return descriptions.get(preset_name, "Custom model configuration")


# Convenience function for getting default configuration
def get_default_config() -> EmbeddingConfig:
    """Get the default embedding configuration"""
    return EmbeddingConfig()


# Example usage and testing
if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    print("=== Embedding Configuration System ===\n")
    
    # Show available presets
    print("Available presets:")
    for name, info in EmbeddingConfig.list_presets().items():
        print(f"  - {name}: {info['model_name']} ({info['dimensions']}d)")
        print(f"    {info['description']}")
    
    print("\n--- Testing configurations ---\n")
    
    # Test default configuration
    config = get_default_config()
    print("Default configuration:")
    for key, value in config.get_config_summary().items():
        print(f"  {key}: {value}")
    
    print("\n--- Testing environment override ---")
    os.environ["RAGEX_EMBEDDING_MODEL"] = "balanced"
    config2 = EmbeddingConfig()
    print(f"Model after env override: {config2.model_name}")
    
    print("\n--- Testing custom model ---")
    custom = ModelConfig(
        model_name="custom/model",
        dimensions=512,
        max_seq_length=300,
        batch_size=24
    )
    config3 = EmbeddingConfig(custom_model=custom)
    print(f"Custom model: {config3.model_name} ({config3.dimensions}d)")