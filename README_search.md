# RAGex Search Client

A command-line search tool for the RAGex indexed codebase with grep-like output.

## Usage

```bash
# Default: Semantic search (natural language queries)
./ragex_search.py "functions that handle authentication"

# Symbol search (literal symbol names)
./ragex_search.py --symbol "process_data"

# Regex search
./ragex_search.py --regex "TODO.*optimization"

# With context lines (like grep -A/-B)
./ragex_search.py -B 3 -A 3 "database connection"
```

## Search Modes

- **Semantic** (default): Natural language search using embeddings. Best for:
  - "functions that validate user input"
  - "code dealing with environment variables"
  - "error handling logic"

- **Symbol** (`--symbol`): Exact symbol name matching. Best for:
  - Finding specific function/class/variable names
  - Case-insensitive whole-word matching

- **Regex** (`--regex`): Regular expression patterns. Best for:
  - Complex pattern matching
  - Finding code patterns like "TODO.*security"

## Options

- `-A NUM, --after-context NUM`: Show NUM lines after each match
- `-B NUM, --before-context NUM`: Show NUM lines before each match
- `--limit NUM`: Maximum number of results (default: 50)

## Prerequisites

Before using semantic search, build the index:

```bash
uv run python scripts/build_semantic_index.py . --stats
```

## Output Format

Results are shown in grep-like format:
```
filename:line_number:matched_content
```

With context lines:
```
filename:line_number-context_before
filename:line_number:matched_line
filename:line_number+context_after
```