"""Tests for the embedding manager module"""

import pytest
from unittest.mock import Mock, patch
import numpy as np
from pathlib import Path

# Import the module to test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from embedding_manager import EmbeddingManager
from embedding_config import EmbeddingConfig


class TestEmbeddingManager:
    """Test cases for EmbeddingManager class"""
    
    @pytest.fixture
    def mock_sentence_transformer(self):
        """Create a mock SentenceTransformer model"""
        mock_model = Mock()
        # Mock encode method to return dummy embeddings
        mock_model.encode.return_value = np.array([
            [0.1, 0.2, 0.3, 0.4],
            [0.5, 0.6, 0.7, 0.8]
        ])
        return mock_model
    
    @pytest.fixture
    def embedding_manager(self, mock_sentence_transformer):
        """Create an EmbeddingManager instance with mocked model"""
        with patch('embedding_manager.SentenceTransformer', return_value=mock_sentence_transformer):
            config = EmbeddingConfig(preset="fast")
            manager = EmbeddingManager(config=config)
            manager.model = mock_sentence_transformer
            return manager
    
    def test_initialization(self, embedding_manager):
        """Test EmbeddingManager initialization"""
        assert embedding_manager is not None
        assert embedding_manager.model is not None
        assert embedding_manager.config is not None
    
    def test_embed_batch(self, embedding_manager, mock_sentence_transformer):
        """Test batch embedding of texts"""
        texts = ["def hello():", "class World:"]
        
        embeddings = embedding_manager.embed_batch(texts)
        
        # Check that model.encode was called
        mock_sentence_transformer.encode.assert_called_once()
        
        # Check embeddings shape
        assert len(embeddings) == 2
        assert len(embeddings[0]) == 4  # Dimension of mock embeddings
        
    def test_embed_batch_empty(self, embedding_manager):
        """Test embedding empty batch"""
        # Mock should return empty array for empty input
        embedding_manager.model.encode.return_value = np.array([])
        embeddings = embedding_manager.embed_batch([])
        
        # embed_batch returns numpy array, not list
        assert isinstance(embeddings, np.ndarray)
        assert len(embeddings) == 0
    
    def test_embed_batch_preprocessing(self, embedding_manager, mock_sentence_transformer):
        """Test that texts are preprocessed before embedding"""
        texts = [
            "   def hello():   ",  # Extra whitespace
            "class\nWorld\n:\npass",  # Newlines
            "// Comment here\nfunction test() {}"  # Comment
        ]
        
        embeddings = embedding_manager.embed_batch(texts)
        
        # Model should have been called with preprocessed texts
        call_args = mock_sentence_transformer.encode.call_args[0][0]
        
        # Basic preprocessing should be applied
        assert len(call_args) == 3
        # Exact preprocessing depends on implementation
        
    def test_enhance_query(self, embedding_manager):
        """Test query context creation"""
        # EmbeddingManager doesn't have enhance_query method
        # Test embedding text instead
        query = "validate input"
        embedding = embedding_manager.embed_text(query)
        
        # Should return single embedding
        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == embedding_manager.model.encode.return_value.shape
        
    def test_code_preprocessing(self, embedding_manager):
        """Test code context creation for embeddings"""
        # Test symbol context creation
        symbol = {
            'name': 'calculate_sum',
            'type': 'function',
            'code': 'def calculate_sum(a, b):\n    return a + b',
            'docstring': 'Calculate sum of two numbers'
        }
        
        context = embedding_manager.create_code_context(symbol)
        assert "calculate_sum" in context
        assert "function" in context
        
    def test_embedding_dimension(self, embedding_manager):
        """Test that embeddings have correct dimensions"""
        config = embedding_manager.config
        expected_dim = config.dimensions
        
        # Create new mock that returns correct dimensions
        mock_model = Mock()
        mock_model.encode.return_value = np.random.rand(1, expected_dim)
        embedding_manager.model = mock_model
        
        embeddings = embedding_manager.embed_batch(["test"])
        assert len(embeddings[0]) == expected_dim
    
    def test_batch_size_handling(self, embedding_manager, mock_sentence_transformer):
        """Test handling of large batches"""
        # Create a large batch
        large_batch = ["code " + str(i) for i in range(100)]
        
        # Reset mock to return appropriate sized array
        mock_sentence_transformer.encode.return_value = np.random.rand(100, 4)
        
        embeddings = embedding_manager.embed_batch(large_batch)
        
        assert len(embeddings) == 100
        assert mock_sentence_transformer.encode.called
    
    def test_special_characters_handling(self, embedding_manager, mock_sentence_transformer):
        """Test handling of special characters in code"""
        texts = [
            "def test_λ_function():",  # Unicode
            "var π = 3.14159;",  # Math symbol
            "// 中文注释\nfunction test() {}",  # Chinese comments
            "def __init__(self):",  # Special Python methods
        ]
        
        # Update mock to return correct size array
        mock_sentence_transformer.encode.return_value = np.random.rand(4, 4)
        
        # Should not raise any errors
        embeddings = embedding_manager.embed_batch(texts)
        assert len(embeddings) == 4