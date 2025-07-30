# Python CLI Implementation Plan for RageX

## Overview

Replace the current bash-based `ragex` wrapper with a robust Python CLI using modern best practices. This will provide better error handling, cross-platform support, and a superior developer experience.

## Technology Choices

### CLI Framework: Typer
- Built on Click but with modern Python type hints
- Automatic help generation from docstrings
- Built-in completion support
- Excellent error messages
- Rich terminal output support

### Additional Libraries
- `docker-py`: Native Python Docker API client
- `rich`: Beautiful terminal output and progress bars
- `pydantic`: Configuration validation
- `platformdirs`: Cross-platform config/data directories

## Architecture

```
ragex-cli/
├── __main__.py          # Entry point
├── cli.py               # Main CLI app with Typer
├── commands/
│   ├── __init__.py
│   ├── index.py         # Index command
│   ├── search.py        # Search command
│   ├── daemon.py        # Daemon management
│   ├── project.py       # Project listing/management
│   └── log.py           # Log viewing
├── core/
│   ├── __init__.py
│   ├── docker.py        # Docker interactions
│   ├── daemon.py        # Daemon lifecycle
│   ├── project.py       # Project ID generation
│   └── config.py        # Configuration management
└── utils/
    ├── __init__.py
    ├── terminal.py      # Rich terminal output
    └── validation.py    # Input validation
```

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1)
1. Set up project structure with proper packaging
2. Implement core Docker client wrapper
3. Create project ID generation matching current logic
4. Basic daemon lifecycle management

### Phase 2: Command Migration (Week 2)
1. Implement all current commands:
   - `index` - with progress bar for indexing
   - `search` - with rich output formatting
   - `serve` - maintain JSON-RPC compatibility
   - `ls/list-projects` - table output with Rich
   - `log` - with better filtering options
   - `init` - with interactive .mcpignore creation
2. Maintain backward compatibility with current behavior

### Phase 3: Enhanced Features (Week 3)
1. Add new commands:
   - `ragex doctor` - Check Docker, permissions, disk space
   - `ragex config` - Manage settings interactively
   - `ragex upgrade` - Update Docker image
   - `ragex stats` - Show indexing statistics
2. Implement shell completion for bash/zsh/fish
3. Add `--json` output mode for all commands

### Phase 4: Testing & Polish (Week 4)
1. Comprehensive test suite with pytest
2. Cross-platform testing (Windows, macOS, Linux)
3. Performance optimization
4. Documentation and migration guide

## Key Implementation Details

### 1. Argument Parsing Example

```python
import typer
from typing import Optional
from pathlib import Path

app = typer.Typer(help="RageX - Intelligent code search for AI assistants")

@app.command()
def index(
    path: Path = typer.Argument(Path("."), help="Path to index"),
    force: bool = typer.Option(False, "--force", "-f", help="Force reindex"),
    model: str = typer.Option("fast", "--model", "-m", help="Embedding model"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Minimal output"),
):
    """Build semantic index for your codebase."""
    # Implementation here
```

### 2. Docker Interaction

```python
import docker
from docker.errors import DockerException, NotFound

class DockerManager:
    def __init__(self):
        try:
            self.client = docker.from_env()
        except DockerException as e:
            raise EnvironmentError(
                "Docker not available. Please ensure Docker is installed and running.\n"
                f"Error: {e}"
            )
    
    def start_daemon(self, project_id: str, config: ProjectConfig) -> Container:
        """Start daemon with proper error handling and retry logic."""
        # Implementation
```

### 3. Rich Output Example

```python
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

def list_projects():
    table = Table(title="RageX Projects")
    table.add_column("Project", style="cyan")
    table.add_column("Path", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Indexed", style="magenta")
    
    # Add rows...
    console.print(table)
```

### 4. Configuration Management

```python
from pydantic import BaseSettings
from platformdirs import user_config_dir

class RagexConfig(BaseSettings):
    docker_image: str = "ragex:local"
    embedding_model: str = "fast"
    daemon_timeout: int = 60
    
    class Config:
        env_prefix = "RAGEX_"
        env_file = Path(user_config_dir("ragex")) / "config.toml"
```

## Backward Compatibility

1. **Command Structure**: Keep exact same command names and basic args
2. **Environment Variables**: Honor all existing RAGEX_* variables
3. **Project IDs**: Use identical hash generation algorithm
4. **Docker Volumes**: Same naming scheme for data persistence
5. **Exit Codes**: Match current exit codes for scripting

## Migration Strategy

1. **Parallel Installation**: 
   - Ship as `ragex-py` initially
   - Allow side-by-side testing
   
2. **Feature Parity First**:
   - Ensure all current functionality works
   - Add comprehensive tests comparing outputs
   
3. **Gradual Transition**:
   - Update documentation to recommend Python version
   - Provide migration script for config/data
   - Eventually make `ragex` symlink to Python version

## Benefits for AI Assistant Users

1. **Better Error Messages**: 
   - Clear explanations when things go wrong
   - Suggestions for fixes
   - No cryptic bash errors

2. **Interactive Features**:
   - Prompts for missing required arguments
   - Confirmation for destructive operations
   - Progress bars for long operations

3. **Discoverability**:
   - `ragex --help` shows all commands with examples
   - `ragex COMMAND --help` shows detailed command help
   - Shell completion for exploring options

4. **Reliability**:
   - Proper signal handling
   - Graceful degradation when Docker issues occur
   - Automatic retry with exponential backoff

## Success Metrics

1. **Performance**: Command startup time < 100ms
2. **Compatibility**: 100% backward compatible
3. **Testing**: >90% code coverage
4. **Platform Support**: Works on Windows (native), macOS, Linux
5. **User Experience**: Reduced support issues by 50%

## Timeline

- Week 1: Core infrastructure and Docker integration
- Week 2: Command migration and feature parity
- Week 3: Enhanced features and polish
- Week 4: Testing, documentation, and release prep
- Week 5: Beta release and feedback collection
- Week 6: GA release

## Example Usage Comparison

### Current (Bash)
```bash
$ ragex index .
🚀 Starting ragex daemon for mcp-ragex...
✅ Socket daemon is ready
🔍 Scanning workspace for changes...
📝 Updating index: +88 ~0 -0 files
✅ Index updated successfully
```

### New (Python)
```bash
$ ragex index .
🚀 Starting ragex daemon for mcp-ragex...
  Docker image: ragex:local ✓
  Container: ragex_daemon_8375a7fd ✓
  Socket: /tmp/ragex.sock ✓
  
📊 Indexing /home/user/projects/mcp-ragex
  ⠋ Scanning files... 1,234 found
  ⠙ Computing checksums... 523/1,234
  ⠹ Extracting symbols... 89%
  ✓ Indexed 1,234 files with 5,678 symbols in 2.3s
  
💡 Tip: Use 'ragex search <query>' to search your codebase
```