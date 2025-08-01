# RAGex Regression Test Suite Plan

## Current Test Coverage Analysis

### Existing Tests
The current test suite focuses on **internal components** rather than **end-to-end CLI functionality**:

**Unit Tests (15+ files):**
- `test_server.py` - MCP server functionality (direct API calls)
- `test_mcp_protocol.py` - MCP protocol integration
- `test_vector_store.py` - ChromaDB vector storage
- `test_embedding_manager.py` - Embedding model management
- `test_tree_sitter*.py` - AST parsing and symbol extraction
- `test_pattern_matching.py` - Pattern matching logic
- `test_indexer.py` - Indexing functionality
- `test_ignore_system.py` - .mcpignore file handling
- `test_watchdog*.py` - File watching and incremental updates

**Integration Tests:**
- `test_hybrid_approach.py` - Combined semantic/symbol/regex search
- `test_enhanced_*.py` - Enhanced symbol extraction features

### RAGex CLI Functionality (From `ragex --help`)

**Core Commands:**
1. **Project Management:**
   - `ragex index [path]` - Build semantic index and start daemon
   - `ragex start` - Index current directory (alias for `index .`)
   - `ragex stop` - Stop daemon if running
   - `ragex status` - Check daemon status

2. **Search Operations:**
   - `ragex search "query"` - Semantic search (default)
   - `ragex search "query" --symbol` - Symbol search mode
   - `ragex search "query" --regex` - Regex search mode
   - `ragex search "query" --json` - JSON output format
   - `ragex search "query" --limit N` - Limit results

3. **Project Administration:**
   - `ragex ls` - List all projects
   - `ragex ls -l` - List with details (model, index status)
   - `ragex ls "pattern"` - List projects matching glob
   - `ragex rm "pattern"` - Remove projects by ID or glob
   - `ragex info` - Show current project information

4. **System Operations:**
   - `ragex log [project] [-f]` - Show/follow daemon logs
   - `ragex register` - Show registration command
   - `ragex unregister` - Show unregistration command
   - `ragex --mcp` - Run as MCP server

5. **Environment Variables:**
   - `RAGEX_EMBEDDING_MODEL` - fast/balanced/accurate
   - `RAGEX_PROJECT_NAME` - Override project name
   - `RAGEX_DOCKER_IMAGE` - Docker image to use
   - `RAGEX_DEBUG` - Enable debug output

## Test Coverage Gaps

### Critical Gaps (Not Tested)
1. **CLI Command Interface** - No tests call actual `ragex` commands
2. **End-to-End Workflows** - No full index → search → cleanup cycles
3. **Project Isolation** - No tests verify multi-project functionality
4. **Docker Integration** - No tests verify containerized behavior
5. **Error Handling** - Limited CLI error scenario coverage
6. **Performance Regression** - No benchmarks for search speed
7. **Data Persistence** - No tests verify data survives daemon restarts

### Moderate Gaps
1. **Configuration Testing** - Environment variable handling
2. **Cross-Platform Testing** - Linux/macOS/Windows compatibility
3. **Resource Management** - Memory/disk usage under load
4. **Concurrent Operations** - Multiple simultaneous searches
5. **Large Codebase Testing** - Performance with real-world projects

## Proposed Regression Test Suite

### Phase 1: CLI Integration Tests (`tests/integration/`)

#### Core Workflow Tests (`test_cli_workflows.py`)
```python
class TestCLIWorkflows:
    def test_basic_workflow(self):
        """Test: start → search → stop"""
        
    def test_project_lifecycle(self):
        """Test: index → info → ls → rm"""
        
    def test_search_modes(self):
        """Test: semantic, symbol, regex search modes"""
        
    def test_multi_project_isolation(self):
        """Test: multiple projects don't interfere"""
```

#### Command-Specific Tests (`test_cli_commands.py`)
```python
class TestIndexCommand:
    def test_index_current_directory(self)
    def test_index_specific_path(self)
    def test_index_with_force_rebuild(self)
    def test_index_with_custom_name(self)
    def test_index_invalid_path(self)  # Error handling

class TestSearchCommand:
    def test_semantic_search(self)
    def test_symbol_search(self)
    def test_regex_search(self)
    def test_json_output_format(self)
    def test_limit_parameter(self)
    def test_empty_results(self)
    def test_invalid_regex(self)  # Error handling

class TestProjectManagement:
    def test_list_projects(self)
    def test_list_with_details(self)
    def test_list_with_pattern(self)
    def test_remove_by_pattern(self)
    def test_project_info(self)
```

#### System Tests (`test_cli_system.py`)
```python
class TestDaemonManagement:
    def test_daemon_lifecycle(self)  # start → status → stop
    def test_daemon_auto_restart(self)
    def test_daemon_logs(self)
    
class TestEnvironmentVariables:
    def test_embedding_model_override(self)
    def test_project_name_override(self)
    def test_debug_mode(self)
```

### Phase 2: End-to-End Tests (`tests/e2e/`)

#### Real Project Tests (`test_real_projects.py`)
```python
class TestRealProjects:
    def test_small_python_project(self):
        """Test on ~100 file Python codebase"""
        
    def test_javascript_project(self):
        """Test on ~100 file JS/TS codebase"""
        
    def test_mixed_language_project(self):
        """Test polyglot codebase"""
        
    def test_medium_codebase_performance(self):
        """Performance benchmark on medium project (~1K files)"""
```

#### MCP Integration Tests (`test_mcp_integration.py`)
```python
class TestMCPIntegration:
    def test_mcp_server_startup(self)
    def test_mcp_search_functionality(self)
    def test_mcp_error_handling(self)
    def test_mcp_with_claude_code(self)  # If possible
```

### Phase 3: Regression Tests (`tests/regression/`)

#### Performance Benchmarks (`test_performance.py`)
```python
class TestPerformance:
    def test_index_speed_benchmark(self)
    def test_search_speed_benchmark(self)
    def test_memory_usage_limits(self)
    def test_concurrent_search_performance(self)
```

#### Data Integrity Tests (`test_data_integrity.py`)
```python
class TestDataIntegrity:
    def test_index_persistence_after_restart(self)
    def test_incremental_updates(self)
    def test_project_data_cleanup(self)
    def test_corruption_recovery(self)
```

## Test Infrastructure Design

### Test Utilities (`tests/utils/`)
```python
# test_helpers.py
class RAGexTestHelper:
    def create_test_project(self, language: str, size: str)
    def run_ragex_command(self, cmd: list) -> subprocess.Result
    def assert_search_results(self, results: dict, expected: dict)
    def cleanup_test_projects(self)
    
# fixtures.py
@pytest.fixture
def temp_python_project():
    """Creates temporary Python project for testing"""
    
@pytest.fixture 
def ragex_daemon():
    """Ensures ragex daemon is running for tests"""
```

### Test Data (`tests/fixtures/`)
- `python_project/` - Sample Python codebase (~50 files)
- `javascript_project/` - Sample JS/TS codebase (~50 files)  
- `medium_project/` - Performance testing project (~500 files)
- `edge_cases/` - Special characters, unicode, etc.

## CI/CD Integration Strategy

### GitHub Actions Workflow (`.github/workflows/test.yml`)

#### Test Matrix
```yaml
strategy:
  matrix:
    os: [ubuntu-latest, macos-latest]  # Skip Windows initially
    python-version: [3.10, 3.11, 3.12]
    test-type: [unit, integration, e2e-small]
```

#### CI-Friendly Tests (Fast, Reliable)
1. **Unit Tests** - All existing component tests (< 2 minutes)
2. **CLI Integration Tests** - Command parsing, basic workflows (< 5 minutes)
3. **Small Project Tests** - Synthetic test projects ~50 files (< 10 minutes)
4. **Error Handling Tests** - Invalid inputs, missing files (< 2 minutes)

#### CI-Challenging Tests (Slow, Resource-Intensive)
1. **Medium Project Tests** - ~500 files (20+ minutes indexing)
2. **Large Project Tests** - Real codebases (1+ hours)
3. **Performance Benchmarks** - Sensitive to CI environment
4. **Docker Integration** - Requires Docker daemon setup
5. **MCP Server Tests** - Complex async protocol testing

### Recommended CI Strategy
1. **Pull Request Tests**: Unit + Integration + Small E2E only (~15 minutes)
2. **Nightly Tests**: Full regression suite including medium projects
3. **Weekly Tests**: Large project performance benchmarks
4. **Release Tests**: All tests + comprehensive benchmarks
5. **Local Development**: Fast subset via `make test-quick`

## Implementation Phases

### Phase 1: Foundation (Week 1)
- [ ] Set up pytest configuration with proper timeouts
- [ ] Create test utilities and fixtures for small projects
- [ ] Implement basic CLI workflow tests
- [ ] Add fast tests to CI pipeline

### Phase 2: Coverage (Week 2)
- [ ] Command-specific test coverage
- [ ] Error handling scenarios
- [ ] Environment variable testing
- [ ] Small project performance baseline

### Phase 3: Advanced (Week 3)
- [ ] Medium-size project tests (nightly only)
- [ ] MCP integration testing
- [ ] Regression benchmark suite
- [ ] Documentation and maintenance guides

## Success Metrics

### Coverage Targets
- **CLI Commands**: 100% command coverage
- **Error Scenarios**: 80% error path coverage
- **Search Modes**: 100% search type coverage
- **Project Operations**: 100% lifecycle coverage

### Performance Targets (Based on Current Performance)
- **Small Projects** (~100 files): < 1 minute indexing
- **Medium Projects** (~500 files): < 5 minutes indexing  
- **Large Projects** (~2K files): < 20 minutes indexing
- **Search Speed**: < 2s for semantic search (any project size)
- **Memory Usage**: < 1GB for medium projects
- **Startup Time**: < 10s daemon initialization

### Quality Targets
- **CI Success Rate**: > 95% test pass rate
- **Test Execution Time**: < 15 minutes for PR tests
- **Flaky Test Rate**: < 2% of tests
- **Bug Detection**: Catch 90% of regressions before release

## Maintenance Strategy

### Test Organization
- Tests mirror CLI command structure
- Clear separation: unit → integration → e2e-small → e2e-large
- Shared utilities for common operations
- Comprehensive documentation with performance expectations

### Continuous Improvement
- Monthly performance benchmark reviews
- Quarterly test suite health checks
- Regular test data updates
- Community contribution guidelines

## Test Execution Strategy

### Local Development
```bash
make test-quick          # Unit + Integration (~5 minutes)
make test-small-e2e      # + Small E2E tests (~15 minutes)  
make test-full           # All tests including medium projects (~45 minutes)
```

### CI Pipeline
```yaml
# Fast PR Tests (~15 minutes)
- Unit tests
- CLI integration tests  
- Small project E2E tests

# Nightly Tests (~2 hours)
- All PR tests
- Medium project tests
- Performance regression checks

# Weekly Full Suite (~4 hours)
- All tests
- Large project benchmarks
- Cross-platform validation
```

## Conclusion

The current test suite provides excellent **component-level coverage** but lacks **end-to-end CLI testing**. The proposed regression test suite fills this gap with realistic performance expectations:

1. **Comprehensive CLI command testing** (fast, CI-friendly)
2. **Tiered project size testing** (small → medium → large)
3. **Performance regression detection** (with realistic targets)
4. **Practical CI/CD integration** (respecting indexing time constraints)
5. **Maintainable test architecture** (clear separation of test types)

This approach balances thorough testing with CI practicality, acknowledging the current indexing performance characteristics while providing a framework for performance improvements.