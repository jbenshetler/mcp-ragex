# `ragex` : Semantic Search for Code with a an MCP Interface
by Jeff Benshetler

2025-09-10

## Introduction
In January of 2025, along with many others, I began using coding agents. Most of my time was spent in Claude Code. This was started as a learning experience, a way to become familiar with and evaluate a new tool. Rather than apply this in a vacuum, I started work on a personal project.

I learn best by application. I want to more easily locate files from my hard drive and am not satisfied with existing commercial or open source solutions. So, for a couple of years I had been off-and-on playing with ElasticSearch. However, I had only been able to create a partially working solution that was later sabotaged by a licensing change. To do this, I pivoted to OpenSearch used Claude Code to help with the configuration. Over time, this grew into a much larger project due to external interest. 

While I was pleased with the help Claude Code provided, I was stymied by the dreaded `Compacting Conversation`, delayed by the slow `Seaching` tools calls, and frustrated by how often it would recreate existing functionality. When Claude Code added support for in April, 2025, I decided to do something about this. 

## Requirements
1. Speed regular expression searches
1. Support semantic searches
1. Callable by MCP

## Design Decisions
1. MCP server implemented using PyPi's `mcp` package.
1. Regular expression searches implemented using `ripgrep`.
1. Analyze language files using tree sitter.
1. Local first LLM for privacy and cost control. 
1. Use generic embedding rather than source code specific embedding for performance.
1. Use ChromaDB to store vectors for simplicity. 
1. Containerize application for easy installation and security. 
1. Need different modes to balance 

### MCP Server
Initially creating an MCP server using the `mcp[cli]` package to expose `ripgrep` was surprisingly easy, using the `stdio` model. This later became more complicated, as it is necessary to trap logs and status updates from various libraries and tools in use to avoid confusing the client. The auto-discovery of the server's capabilities and parameters by the client works well.

[Creating the server](../src/server.py#241)


### Regex searching
Claude Code's default is to use regular expressions to search. At the time I created this tool, Claude used `grep`, which is single threaded and slow compared to the parallel `ripgrep`.

### Semantic Search
Semantic searching requires finding the files, chunking them, creating vector embeddings, storing the vector embeddings in a database that faciliates 

```
ragex - search_code_simple (MCP)(query: "Symbol creation with signature docstring code fields")
  ⎿  # Searching for 'Symbol creation with signature docstring code fields' using semantic mode
     # Found 33 matches
     /home/jeff/clients/mcp-ragex/src/ragex_core/embedding_manager.py::[function] (0.434) create_code_context(self, symbol: Dict)
     /home/jeff/clients/mcp-ragex/src/parallel_symbol_extractor.py::[function] (0.356) extract_symbols_from_files
     /home/jeff/clients/mcp-ragex/src/tree_sitter_enhancer.py::[function] (0.355) extract_symbols
     /home/jeff/clients/mcp-ragex/src/tree_sitter_enhancer.py::[function] (0.352) get_file_symbols(self, file_path: str)
     /home/jeff/clients/mcp-ragex/src/tree_sitter_enhancer.py::[function] (0.349) _extract_python_symbols
     /home/jeff/clients/mcp-ragex/src/tree_sitter_enhancer.py::[function] (0.331) _extract_docstring(self, node, source: bytes, lang: str)
     /home/jeff/clients/mcp-ragex/src/indexer.py::[function] (0.322) extract_symbols_from_file(self, file_path: Path)
     /home/jeff/clients/mcp-ragex/src/ragex_core/vector_store.py::[function] (0.315) add_symbols
     /home/jeff/clients/mcp-ragex/src/ragex_core/result_formatters.py::[function] (0.313) format_results
   
```

### Parse languages using tree sitter
A tree sitter approach gets most of the languages nuances right without requiring the complexity of a full parser. For many languages, a full parser requires an impractical amount of configuration for search paths, compiler options, etc., to be practical. Tree sitters are available for the languages of my immediate interest: Python, C++, JavaScript/TypeScript.

[Tree Sitter](../src/tree_sitter_enhancer.py)


The tree sitter provides natural chunking, with the most salient chunk being function name and associated signature. So when generating embeddings for functions and classes, the system creates rich context that includes:

  1. Basic metadata: Type, name, language, file
  1. Signature: Function/method signature
  1. Docstring: The full docstring content
  1. Parent context: Parent class/module
  1. Keywords: Extracted from code
  1. Function calls: Dependencies found in code
  1. Code snippet: Actual code content

  This means that when searching for something related to a function's purpose or behavior, the embedding will match not just the function name and signature, but also
  the semantic meaning described in its docstring.

  For example, if a function has a docstring saying "Calculate the total price including tax", a search for "calculate price tax" will match that function even if those
  exact words aren't in the function name.

[Embedding Manager](../src/ragex_core/embedding_manager.py)
 * `_create_default_context` L329-330

### Local first
Since this project targets not the general public but developers using coding agents, the assumption is that they have either a GPU or a sufficiently powerful CPU to compute the embeddings locally. This preserves the code privacy. 

[Embedding Manager](../src/ragex_core/embedding_manager.py)
 * `embed_code_symbols` L427

### Containerize application
Source files are mounted inside the container and the reported path needs to be relative to the host. There is path translation that has to happen. 
1. Security
1. Installation Ease
1. Isolation


### Semantic searching
In my usage, Claude regularly re-creates existing functionality in non-trivial code, likely due to not only a limited context window but also context rot. Beyond the searching being slow, the coding agent's review is slow and consumes a large number of tokens, compounding the forgetting problem. 
## Challenges
### TokensYou 
### Security
Users righfully have security concerns. 
#### Model

## Improvements
1. Layered Docker images for faster builds.
1. Progress bars while indexing.
1. Support for remote embedding computation with batching. 
1. 

## References
1. "Context Rot: How Increasing Input Tokens Impacts LLM Performance" by Kelly Hong, Anton Troynikov, and Jeff Huber, https://research.trychroma.com/context-rot
1. Claude Code Release Notes, https://claudelog.com/faqs/claude-code-release-notes/
1. 