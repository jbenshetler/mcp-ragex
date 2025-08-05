"""Tests for the indexer module"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

# Import the module to test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from indexer import CodeIndexer
from embedding_config import EmbeddingConfig


class TestCodeIndexer:
    """Test cases for CodeIndexer class"""
    
    @pytest.fixture
    def temp_project_dir(self):
        """Create a temporary project directory with test files"""
        temp_dir = tempfile.mkdtemp()
        
        # Create test Python file
        python_file = Path(temp_dir) / "test.py"
        python_file.write_text("""
def hello_world():
    '''A simple hello world function'''
    print("Hello, World!")

class TestClass:
    '''A test class'''
    def __init__(self):
        self.value = 42
        
    def get_value(self):
        return self.value
""")
        
        # Create test JavaScript file
        js_file = Path(temp_dir) / "test.js"
        js_file.write_text("""
function greet(name) {
    console.log(`Hello, ${name}!`);
}

class Calculator {
    constructor() {
        this.result = 0;
    }
    
    add(a, b) {
        return a + b;
    }
}
""")
        
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def temp_db_dir(self):
        """Create a temporary directory for the database"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def mock_embedding_manager(self):
        """Create a mock embedding manager"""
        mock = Mock()
        mock.embed_batch.return_value = [[0.1, 0.2, 0.3]] * 10  # Return dummy embeddings
        return mock
    
    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store"""
        mock = Mock()
        mock.add_embeddings.return_value = None
        mock.get_all_symbols.return_value = {'ids': [], 'metadatas': [], 'documents': []}
        return mock
    
    @pytest.fixture
    def indexer(self, temp_project_dir, temp_db_dir, mock_embedding_manager, mock_vector_store):
        """Create a CodeIndexer instance with mocked dependencies"""
        # Change to temp project dir to simulate project context
        import os
        original_cwd = os.getcwd()
        os.chdir(temp_project_dir)
        
        try:
            with patch('indexer.EmbeddingManager', return_value=mock_embedding_manager):
                with patch('indexer.CodeVectorStore', return_value=mock_vector_store):
                    config = EmbeddingConfig(preset="fast")
                    indexer = CodeIndexer(
                        persist_directory=temp_db_dir,
                        config=config
                    )
                    indexer.embedding_manager = mock_embedding_manager
                    indexer.vector_store = mock_vector_store
                    return indexer
        finally:
            os.chdir(original_cwd)
    
    def test_initialization(self, indexer):
        """Test CodeIndexer initialization"""
        assert indexer is not None
        assert indexer.config is not None
        assert indexer.embedding_manager is not None
        assert indexer.vector_store is not None
    
    @pytest.mark.asyncio
    async def test_extract_symbols_from_file(self, indexer, temp_project_dir):
        """Test extracting symbols from a Python file"""
        python_file = Path(temp_project_dir) / "test.py"
        symbols = await indexer.extract_symbols_from_file(python_file)
        
        # Should find at least the function and class
        assert len(symbols) >= 2
        
        # Check for function
        func_symbols = [s for s in symbols if s['name'] == 'hello_world']
        assert len(func_symbols) == 1
        assert func_symbols[0]['type'] == 'function'
        assert 'A simple hello world function' in func_symbols[0]['code']
        
        # Check for class
        class_symbols = [s for s in symbols if s['name'] == 'TestClass']
        assert len(class_symbols) == 1
        assert class_symbols[0]['type'] == 'class'
    
    def test_find_code_files(self, indexer, temp_project_dir):
        """Test finding code files in project"""
        files = list(indexer.find_code_files())
        
        # Should find both test files
        assert len(files) == 2
        file_names = [f.name for f in files]
        assert 'test.py' in file_names
        assert 'test.js' in file_names
    
    @pytest.mark.asyncio
    async def test_index_project(self, indexer, temp_project_dir, mock_embedding_manager, mock_vector_store):
        """Test indexing an entire project"""
        # Run indexing
        stats = await indexer.index_codebase(force=True)
        
        # Check stats
        assert stats['total_files'] == 2
        assert stats['total_symbols'] > 0
        assert stats['languages']['Python'] > 0
        assert stats['languages']['JavaScript'] > 0
        
        # Verify embedding manager was called
        assert mock_embedding_manager.embed_batch.called
        
        # Verify vector store was called
        assert mock_vector_store.add_embeddings.called
    
    def test_ignore_patterns(self, temp_project_dir, temp_db_dir):
        """Test that ignore patterns work correctly"""
        # Create files that should be ignored
        (Path(temp_project_dir) / "__pycache__").mkdir()
        (Path(temp_project_dir) / "__pycache__" / "test.pyc").write_text("compiled")
        (Path(temp_project_dir) / "node_modules").mkdir()
        (Path(temp_project_dir) / "node_modules" / "test.js").write_text("module")
        (Path(temp_project_dir) / ".git").mkdir()
        (Path(temp_project_dir) / ".git" / "config").write_text("git config")
        
        # Create indexer without mocks to test pattern matching
        import os
        original_cwd = os.getcwd()
        os.chdir(temp_project_dir)
        
        try:
            with patch('indexer.EmbeddingManager'):
                with patch('indexer.CodeVectorStore'):
                    config = EmbeddingConfig(preset="fast")
                    indexer = CodeIndexer(
                        persist_directory=temp_db_dir,
                        config=config
                    )
                
                # Find code files
                files = list(indexer.find_code_files())
                file_paths = [str(f) for f in files]
                
                # Verify ignored files are not included
                assert not any('__pycache__' in p for p in file_paths)
                assert not any('node_modules' in p for p in file_paths)
                assert not any('.git' in p for p in file_paths)
                
                # Original test files should still be found
                assert len(files) == 2
        finally:
            os.chdir(original_cwd)
    
    @pytest.mark.asyncio
    async def test_symbol_extraction_error_handling(self, indexer, temp_project_dir):
        """Test error handling when extracting symbols"""
        # Create a file with invalid syntax
        bad_file = Path(temp_project_dir) / "bad.py"
        bad_file.write_text("def incomplete_function(")
        
        # Should handle the error gracefully
        symbols = await indexer.extract_symbols_from_file(bad_file)
        
        # May return empty list or partial results depending on tree-sitter behavior
        assert isinstance(symbols, list)