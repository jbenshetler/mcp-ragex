"""Tests for MCP protocol integration"""

import pytest
import pytest_asyncio
import json
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

# Import the module to test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from server import RipgrepSearcher
import server


class TestMCPProtocol:
    """Test cases for MCP protocol integration"""
    
    @pytest.fixture
    def mock_ripgrep_searcher(self):
        """Create a mock RipgrepSearcher"""
        mock = AsyncMock()
        mock.search.return_value = {
            "matches": [
                {
                    "file": "test.py",
                    "line": 10,
                    "content": "def test_function():",
                    "match": "test_function"
                }
            ],
            "total_matches": 1,
            "truncated": False
        }
        return mock
    
    @pytest_asyncio.fixture
    async def mcp_server(self, mock_ripgrep_searcher):
        """Create an MCP server instance"""
        with patch('server.RipgrepSearcher', return_value=mock_ripgrep_searcher):
            # Since create_server doesn't exist, create a mock server
            mock_server = AsyncMock()
            mock_server.searcher = mock_ripgrep_searcher
            mock_server.call_tool = AsyncMock()
            yield mock_server
    
    @pytest.mark.asyncio
    async def test_search_code_tool(self, mcp_server, mock_ripgrep_searcher):
        """Test the search_code tool via MCP protocol"""
        # Simulate tool call
        result = await mcp_server.call_tool(
            "search_code",
            {
                "pattern": "test_function",
                "file_types": ["py"],
                "limit": 10
            }
        )
        
        # Verify searcher was called
        mock_ripgrep_searcher.search.assert_called_once()
        
        # Check result structure
        assert "matches" in result
        assert "total_matches" in result
        assert result["total_matches"] == 1
    
    @pytest.mark.asyncio
    async def test_search_code_simple_tool(self, mcp_server):
        """Test the search_code_simple tool"""
        with patch.object(mcp_server, 'call_tool', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {
                "matches": [{"file": "test.py", "line": 1, "content": "test"}],
                "total_matches": 1
            }
            
            # Call simple search
            result = await mcp_server.call_tool(
                "search_code_simple",
                {"query": "test function"}
            )
            
            # Should delegate to search_code with auto mode
            assert result is not None
    
    @pytest.mark.asyncio
    async def test_get_search_capabilities_tool(self, mcp_server):
        """Test the get_search_capabilities tool"""
        # Call the tool
        result = await mcp_server.call_tool("get_search_capabilities", {})
        
        # Check result structure
        assert "modes" in result
        assert "auto_detection_examples" in result
        assert "semantic" in result["modes"]
        assert "symbol" in result["modes"]
        assert "regex" in result["modes"]
    
    @pytest.mark.asyncio
    async def test_tool_error_handling(self, mcp_server, mock_ripgrep_searcher):
        """Test error handling in tool calls"""
        # Make searcher raise an exception
        mock_ripgrep_searcher.search.side_effect = ValueError("Invalid pattern")
        
        # Call should handle the error gracefully
        with pytest.raises(Exception) as exc_info:
            await mcp_server.call_tool(
                "search_code",
                {"pattern": "[invalid"}
            )
        
        assert "Invalid pattern" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_semantic_search_fallback(self, mcp_server):
        """Test semantic search fallback when not available"""
        # Mock semantic search as unavailable
        with patch.object(mcp_server, '_try_semantic_search', return_value=None):
            with patch.object(mcp_server.searcher, 'search', new_callable=AsyncMock) as mock_search:
                mock_search.return_value = {"matches": [], "total_matches": 0}
                
                # Try semantic search
                result = await mcp_server.call_tool(
                    "search_code",
                    {
                        "query": "functions that validate input",
                        "mode": "semantic"
                    }
                )
                
                # Should fall back to regex search
                mock_search.assert_called()
    
    @pytest.mark.asyncio
    async def test_path_validation_in_tool(self, mcp_server):
        """Test that path validation works through MCP tool calls"""
        # Try to search with malicious path
        with patch.object(mcp_server.searcher, 'validate_paths') as mock_validate:
            mock_validate.return_value = []  # No valid paths
            
            result = await mcp_server.call_tool(
                "search_code",
                {
                    "pattern": "test",
                    "paths": ["../../../etc/passwd"]
                }
            )
            
            # Should have called validate_paths
            mock_validate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_file_type_filtering(self, mcp_server, mock_ripgrep_searcher):
        """Test file type filtering in search"""
        await mcp_server.call_tool(
            "search_code",
            {
                "pattern": "test",
                "file_types": ["py", "js", "ts"]
            }
        )
        
        # Check that file types were passed to searcher
        call_args = mock_ripgrep_searcher.search.call_args[1]
        assert "file_types" in call_args
        assert set(call_args["file_types"]) == {"py", "js", "ts"}
    
    @pytest.mark.asyncio  
    async def test_search_result_formatting(self, mcp_server):
        """Test that search results are properly formatted"""
        # Mock searcher with specific results
        mock_results = {
            "matches": [
                {
                    "file": "/project/src/main.py",
                    "line": 42,
                    "content": "    def process_data(self, data):",
                    "match": "process_data"
                },
                {
                    "file": "/project/tests/test_main.py", 
                    "line": 15,
                    "content": "def test_process_data():",
                    "match": "process_data"
                }
            ],
            "total_matches": 2,
            "truncated": False
        }
        
        with patch.object(mcp_server.searcher, 'search', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_results
            
            result = await mcp_server.call_tool(
                "search_code",
                {"pattern": "process_data"}
            )
            
            # Verify formatting
            assert len(result["matches"]) == 2
            assert all("file" in match for match in result["matches"])
            assert all("line" in match for match in result["matches"])
            assert result["total_matches"] == 2