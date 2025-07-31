# MCP Flow Debug Plan

## 1. Test Socket Client MCP Handling
Check if socket_client properly execs the MCP server:
```bash
docker exec -it ragex_daemon_ragex_1000_f8902326ad894225 python -c "
import sys
sys.path.append('/app')
from src.socket_client import main
print('Socket client can import')
"
```

## 2. Test MCP Server Direct Execution
Run MCP server directly in container:
```bash
docker exec -it ragex_daemon_ragex_1000_f8902326ad894225 python -m src.mcp_server < /dev/null
```

## 3. Add Debug Logging
Add logging at each step:
- When _handle_search is called
- When SearchClient is initialized
- When run_search is called
- When search completes

## 4. Test SearchClient Initialization
```python
# Inside container
from src.cli.search import SearchClient
client = SearchClient("/data/projects/ragex_1000_f8902326ad894225", json_output=True)
print(f"Client initialized: {client}")
print(f"Semantic searcher: {client.semantic_searcher}")
```

## 5. Test Synchronous Search
Create a minimal test that bypasses async:
```python
# Test if the search itself works
import asyncio
from src.cli.search import SearchClient

client = SearchClient("/data/projects/ragex_1000_f8902326ad894225", json_output=True)
results = asyncio.run(client.search_semantic("test", limit=5))
print(results)
```

## 6. Check for Blocking I/O
- Is ChromaDB connection hanging?
- Is model loading hanging?
- Is there a timeout we need to set?

## 7. Trace Execution
Use strace to see exactly where it hangs:
```bash
strace -f -e trace=read,write,open,connect -p <pid_of_mcp_server>
```