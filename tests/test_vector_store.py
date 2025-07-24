"""Tests for the vector store module"""

import pytest
import tempfile
import shutil
from pathlib import Path
import numpy as np

# Import the module to test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vector_store import CodeVectorStore
from embedding_config import EmbeddingConfig


class TestVectorStore:
    """Test cases for CodeVectorStore class"""
    
    @pytest.fixture
    def temp_db_dir(self):
        """Create a temporary directory for the database"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def vector_store(self, temp_db_dir):
        """Create a CodeVectorStore instance with test configuration"""
        config = EmbeddingConfig(preset="fast")
        return CodeVectorStore(persist_directory=temp_db_dir, config=config)
    
    def test_initialization(self, vector_store):
        """Test VectorStore initialization"""
        assert vector_store is not None
        assert vector_store.collection is not None
        assert vector_store.persist_directory is not None
    
    def test_add_embeddings(self, vector_store):
        """Test adding symbols to the store"""
        # Create test data
        symbols = [
            {"id": "test1", "type": "function", "name": "test_func1", "code": "def test_func1():"},
            {"id": "test2", "type": "class", "name": "TestClass", "code": "class TestClass:"}
        ]
        embeddings = np.array([
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6]
        ])
        
        # Add symbols
        result = vector_store.add_symbols(symbols=symbols, embeddings=embeddings)
        
        # Verify they were added
        assert result['status'] == 'success'
        assert result['count'] == 2
        
    def test_search_similar(self, vector_store):
        """Test searching for similar embeddings"""
        # Add test data
        symbols = [
            {"id": "func1", "type": "function", "name": "func1", "code": "def func1():"},
            {"id": "func2", "type": "function", "name": "func2", "code": "def func2():"},
            {"id": "func3", "type": "function", "name": "func3", "code": "def func3():"}
        ]
        embeddings = np.array([
            [0.1, 0.2, 0.3, 0.4],
            [0.5, 0.6, 0.7, 0.8],
            [0.9, 0.1, 0.2, 0.3]
        ])
        
        vector_store.add_symbols(symbols=symbols, embeddings=embeddings)
        
        # Search for similar
        query_embedding = np.array([0.1, 0.2, 0.3, 0.4])  # Similar to func1
        results = vector_store.search(
            query_embedding=query_embedding,
            n_results=2
        )
        
        assert 'ids' in results
        assert len(results['ids']) <= 2
        
    def test_get_all_symbols(self, vector_store):
        """Test retrieving statistics"""
        # Add test data
        symbols = [
            {"id": "symbol1", "type": "function", "name": "test1", "code": "def test1():"},
            {"id": "symbol2", "type": "class", "name": "Test2", "code": "class Test2:"}
        ]
        embeddings = np.array([[0.1, 0.2], [0.3, 0.4]])
        
        vector_store.add_symbols(symbols=symbols, embeddings=embeddings)
        
        # Get statistics
        stats = vector_store.get_statistics()
        assert stats['total_count'] == 2
        assert 'type_distribution' in stats
        
    def test_delete_by_file(self, vector_store):
        """Test deleting symbols by file path"""
        # Add test data with file paths
        symbols = [
            {"id": "file1_func1", "type": "function", "name": "func1", "code": "def func1():", "file_path": "/path/file1.py"},
            {"id": "file1_func2", "type": "function", "name": "func2", "code": "def func2():", "file_path": "/path/file1.py"},
            {"id": "file2_func1", "type": "function", "name": "func1", "code": "def func1():", "file_path": "/path/file2.py"}
        ]
        embeddings = np.array([[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]])
        
        vector_store.add_symbols(symbols=symbols, embeddings=embeddings)
        
        # Delete symbols from file1
        count = vector_store.delete_by_file("/path/file1.py")
        
        # Verify deletion
        assert count == 2
        stats = vector_store.get_statistics()
        assert stats['total_count'] == 1
        
    def test_clear(self, vector_store):
        """Test clearing all data"""
        # Add test data
        symbols = [
            {"id": "test1", "type": "function", "name": "test", "code": "def test():"},
            {"id": "test2", "type": "class", "name": "Test", "code": "class Test:"}
        ]
        embeddings = np.array([[0.1, 0.2], [0.3, 0.4]])
        
        vector_store.add_symbols(symbols=symbols, embeddings=embeddings)
        
        # Clear the store
        result = vector_store.clear()
        
        # Verify it's empty
        assert result['status'] == 'success'
        stats = vector_store.get_statistics()
        assert stats['total_count'] == 0