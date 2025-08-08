# RAGex MCP Testing for Claude

This directory contains test suites specifically designed to validate the RAGex MCP server's functionality from within Claude's environment, without requiring external shell commands.

## Available Test Suites

### 1. `claude_mcp_test_runner.py` - Quick Validation Tests
**Recommended for regular testing**

Simple, fast tests that validate core MCP functionality:
- Basic search operations
- Semantic search simulation  
- Regex pattern matching
- Symbol search
- File type filtering
- MCP response structure validation
- Error handling

**Usage from Claude:**
```python
# Run quick validation (returns True/False)
from tests.claude_mcp_test_runner import quick_mcp_validation
success = await quick_mcp_validation()
print(f"MCP validation: {'✅ PASS' if success else '❌ FAIL'}")

# Get detailed results
from tests.claude_mcp_test_runner import run_mcp_tests
results = await run_mcp_tests()
print(f"Success rate: {results['summary']['success_rate']:.1f}%")
```

### 2. `test_mcp_ragex_integration.py` - Comprehensive Integration Tests
**For thorough validation**

Extensive tests that create a realistic codebase and test:
- Full semantic search capabilities
- Complex regex patterns
- Symbol resolution
- Multi-language support
- MCP protocol compliance
- Error scenarios

**Usage from Claude:**
```python
from tests.test_mcp_ragex_integration import run_ragex_mcp_tests
exit_code = await run_ragex_mcp_tests()
print(f"Integration tests: {'✅ PASS' if exit_code == 0 else '❌ FAIL'}")
```

## Test Scenarios Covered

### Semantic Search Tests
- Authentication-related code discovery
- File upload functionality detection
- Error handling pattern recognition
- Natural language query processing

### Regex Search Tests  
- TODO comment extraction
- Function definition patterns
- Complex pattern matching
- Case-sensitive/insensitive search

### Symbol Search Tests
- Exact class name matching
- Method name resolution
- Interface detection
- Symbol-based navigation

### MCP Protocol Validation
- Response structure validation
- Error handling compliance
- Tool capability reporting
- Content formatting

## Running Tests

### Prerequisites

1. **Set up Python virtual environment:**
   ```bash
   uv venv
   uv pip install --no-cache-dir -r requirements/cpu-amd64.txt --index-strategy unsafe-best-match
   ```

2. **Activate the virtual environment:**
   ```bash
   source .venv/bin/activate
   ```

### Running the Comprehensive MCP Tests

**With UV dependency management (Recommended):**
```bash
# The UV script automatically installs MCP dependencies
env PYTHONPATH=/home/jeff/clients/mcp-ragex uv run tests/test_mcp_with_uv.py
```

**With activated virtual environment:**
```bash
# Ensure virtual environment is activated first
source .venv/bin/activate
env PYTHONPATH=/home/jeff/clients/mcp-ragex tests/test_mcp_with_uv.py
```

### Running Quick Validation Tests

**From Claude Code CLI:**

The tests are designed to run directly within Claude's Python environment:

```python
# Quick validation
exec(open('tests/claude_mcp_test_runner.py').read())

# Or use the async runner
import asyncio
from tests.claude_mcp_test_runner import run_mcp_tests
results = await run_mcp_tests()
```

### Environment Setup Requirements

**Essential Environment Variables:**
- `PYTHONPATH=/home/jeff/clients/mcp-ragex` - Required to resolve relative imports
- Virtual environment must include all dependencies from `requirements/cpu-amd64.txt`

**Dependencies installed by the commands above:**
- `mcp>=1.0.0` - Model Context Protocol SDK
- `pytest>=7.0.0` - Testing framework  
- `pytest-asyncio>=0.21.0` - Async test support
- `tree-sitter>=0.22.0` - Code parsing (specific version required)
- `sentence-transformers` - Semantic search capabilities
- All other RAGex dependencies

### Test Output Format

Tests provide structured output suitable for analysis:

```json
{
  "summary": {
    "total_tests": 7,
    "passed": 6, 
    "failed": 1,
    "success_rate": 85.7
  },
  "test_details": [
    {
      "name": "Basic Search Functionality",
      "passed": true,
      "details": "Found 3 matches",
      "has_response_data": true
    }
  ]
}
```

## Test Environment

Tests automatically:
1. Create temporary test directories
2. Generate realistic code files in multiple languages
3. Initialize the RAGex searcher
4. Run comprehensive test scenarios  
5. Clean up temporary files
6. Report detailed results

## Key Features for Claude

- **No external dependencies**: Tests run entirely within Python
- **Structured output**: Results in JSON format for easy analysis
- **Detailed validation**: Tests both functionality and MCP protocol compliance
- **Realistic scenarios**: Uses representative code patterns
- **Error resilience**: Graceful handling of test failures
- **Quick feedback**: Fast execution suitable for interactive testing

## Interpreting Results

### Success Criteria
- **80%+ pass rate**: Indicates healthy MCP server functionality
- **Search result structure**: Validates MCP protocol compliance
- **Multi-mode support**: Confirms semantic/regex/symbol capabilities
- **Error handling**: Ensures graceful failure scenarios

### Common Issues
- **Import failures**: May indicate missing dependencies
- **Search failures**: Could indicate ripgrep or indexing issues  
- **Structure validation**: Suggests MCP protocol problems
- **File type filtering**: May indicate configuration issues

## Integration with Development

These tests can be used to:
- Validate MCP server changes
- Test new search features
- Verify protocol compliance
- Debug search functionality
- Benchmark performance

The tests are specifically designed to work within Claude's execution environment and provide comprehensive validation of the RAGex MCP server's capabilities.