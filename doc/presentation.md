# `ragex` : Semantic Search for Code with a an MCP Interface
by Jeff Benshetler

2025-09-10

## Table of Contents
- [`ragex` : Semantic Search for Code with a an MCP Interface](#ragex--semantic-search-for-code-with-a-an-mcp-interface)
  - [Table of Contents](#table-of-contents)
  - [Introduction](#introduction)
  - [Requirements](#requirements)
  - [Design Decisions](#design-decisions)
    - [MCP Server](#mcp-server)
    - [Regex Search with ripgrep](#regex-search-with-ripgrep)
    - [Semantic Search with SentenceTransformer](#semantic-search-with-sentencetransformer)
      - [Model Selection](#model-selection)
      - [Similarity Search](#similarity-search)
      - [Re-ranking](#re-ranking)
    - [Parse Languages Using Tree Sitter](#parse-languages-using-tree-sitter)
    - [Code Indexing](#code-indexing)
    - [Local first](#local-first)
    - [Containerize Application](#containerize-application)
      - [Security](#security)
        - [File Access](#file-access)
      - [Isolation](#isolation)
        - [Network Access](#network-access)
      - [Installation Ease](#installation-ease)
    - [Administration](#administration)
      - [Index Catalog](#index-catalog)
  - [Improvements](#improvements)
  - [References](#references)

## Introduction
In January of 2025, along with many others, I began using coding agents. Most of my time was spent in Claude Code. This was started as a learning experience, a way to become familiar with and evaluate a new tool. Rather than apply this in a vacuum, I started work on a personal project.

I learn best by application. I want to more easily locate files from my hard drive and am not satisfied with existing commercial or open source solutions. So, for a couple of years I had been off-and-on playing with ElasticSearch. However, I had only been able to create a partially working solution that was later sabotaged by a licensing change. To do this, I pivoted to OpenSearch used Claude Code to help with the configuration. Over time, this grew into a much larger project due to external interest. 

While I was pleased with the help Claude Code provided, I was stymied by the dreaded `Compacting Conversation`, delayed by the slow `Seaching` tools calls, and frustrated by how often it would recreate existing functionality. When Claude Code added support for in April, 2025, I decided to do something about this. 

## Requirements
As a developer using LLM coding agents, I want to spend less time waiting for the coding agent to search my code, and for the search results to be more relevant.

1. Speed regular expression searches
1. Support semantic searches
1. Callable by MCP

## Design Decisions


### MCP Server
Initially creating an MCP server using the `mcp[cli]` package to expose `ripgrep` was surprisingly easy, using the `stdio` model. This later became more complicated, as it is necessary to trap logs and status updates from various libraries and tools in use to avoid confusing the client. The auto-discovery of the server's capabilities and parameters by the client works well.

[Creating the server](../src/server.py#241)


### Regex Search with ripgrep
Claude Code's default is to use regular expressions to search. At the time I created this tool, Claude used `grep`, which is single threaded and slow compared to the parallel `ripgrep`.

### Semantic Search with SentenceTransformer

#### Model Selection
SentenceTransformer was selected because of its speed and support in the Python ecosystem. While a code-trained model like [CodeBERT](https://arxiv.org/abs/2002.08155) is the natural approach, it is approximately 10X slower during indexing than the SentenceTransformer models. Because of the chunking done with tree sitter, in practice simpler models work well, at least for languages like Python and JavaScript. Additional challenges with CodeBERT include:

1. SentenceTransformer outputs fixed-sized embeddings optimized for semantic similarity tasks like mean pooling or CLS token extraction vs. CodeBERT requiring additional processing. 
1. The API between the two is different. 
1. SentenceTransformer has built-in batch processing optimization while BERT models require custom batching implementation. 

#### Similarity Search

We are using Approximate Nearest Neighbor (ANN) with the cosine similarity metric implemented as implemented as Hierarchical Navigable Small World.

[Similarity Metric vector_store.py:69](../src/ragex_core/vector_store.py)
[Initial Search vectory_store.py:208](../src/ragex_core/vector_store.py)
[Cosine Distance to Similarity Conversion cli/search.py:132](../src/cli/search.py)


#### Re-ranking

We use re-ranking to adjust the order of results based on simple additive preference weights. For example, we prefer function definitions to constants, and production code to test code. Not involving an LLM in re-ranking allows acceptable performance on CPU-only systems. The primary use case is returning the results to an LLM that will perform its own re-ranking. 

[reranker.py](../src/ragex_core/reranker.py)
 * Weights configuration L27 
 * File-level penalties L145


<details>
    <summary>Sample semantic search for 'Symbol creation with signature docstring code fields'</summary>

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
</details>



### Parse Languages Using Tree Sitter
A tree sitter approach gets most of the languages nuances right without requiring the complexity of a full parser. For many languages, a full parser requires an impractical amount of configuration for search paths, compiler options, etc.. Tree sitters are available for the languages of my immediate interest: Python, C++, JavaScript/TypeScript.

[Tree Sitter](../src/tree_sitter_enhancer.py)


The tree sitter provides natural chunking, with the most salient chunk being function name and associated signature.  So when generating embeddings for functions and classes, the system creates rich context that includes:

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

Variables are specifically not indexed because they often require a broader, ill-defined context to get semantic meaning. 

### Code Indexing
An index is necessary for semantic search to work. The only way to start the per-directory container is using `ragex start`, which builds or intelligently rebuilds the index before launching the container.

[ragex](../ragex)
 * `cmd_start()` L619
 * Index command processing `cmd_index()` L549
 * Ensure the daemon is running `exec_via_daemon()` L317
 * Creates the per-directory container `start_daemon()` L174

Calling `ragex start` from within a directory that already has an index will start that ancestor directory's container rather than create a new one. 



### Local first
Since this project targets not the general public but developers using coding agents, the assumption is that they have either a GPU or a sufficiently powerful CPU to compute the embeddings locally. This preserves the code privacy. 

[Embedding Manager](../src/ragex_core/embedding_manager.py)
 * `embed_code_symbols` L427

### Containerize Application
Source files are mounted inside the container and the reported path needs to be relative to the host. There is path translation that has to happen. 
1. Security
1. Installation Ease
1. Isolation

#### Security

##### File Access
The application is limited to accessing to host files using volume mounts, limited to:
  1. Indexed directory → /workspace (read-only)
    - This is where your project files are mounted when you run `ragex` commands
    - Read-only access prevents accidental modification
  2. User config directory (`$HOME/.config/ragex`) → `/home/ragex/.config/ragex`
    - Stores RAGex configuration files
    - Only mounted in the fallback wrapper [install.sh:170](../install.sh)
  3. User data volume (ragex_user_<user_id>) → `/data`
    - Docker named volume for persistent data (ChromaDB indexes, models, etc.)
    - Isolated per user ID for security
  4. Host home directory path (as environment variable HOST_HOME)
    - Path information only, not mounted as volume
    - Used for path mapping between container and host

#### Isolation
Each directory available for searching (via `ragex start`) runs in a separate Docker container, using the host file permissions to enforce isolation. Individual containers can be stopped using `ragex stop` and can be removed using `ragex rm <project ID | glob>`. 

[ragex](../ragex)
 * Properties that create per-directory isolation L64
 * Creates unique ID per directory L157

##### Network Access
 Additionally, the container does not have network access at all enforced by Docker unless the `--network` flag is passed during installation. [install.sh:18](../install.sh). The network is needed during installation for the host to pull the Docker image. The default model is included as part of the Docker image, therefore no runtime network access is needed by the container. If the user requests additional models, they need to provide network access used during runtime to download the model. Because the model is stored in the persistent volume mount, that mount must exist before the model is downloaded. Non-default models are downloaded when a user first indexes a project.   

 [Networking strategy embedding.py L79-121](../src/ragex_core/embedding_manager.py)
  * First attempt: Offline mode L83-98
  * Second attempt: Network download L23-38

#### Installation Ease
To make this easy to use, being able to have the program in your path and run it as `ragex` is a significant quality-of-live improvement. It relies on non-default Python packages and would otherwise have to run in a virtual environment. CUDA dependencies are notoriously difficult to get right. By packaging the application as a container and using a launch script, `ragex`, eliminates dependency management challenges for the user.

<details>
<summary>Recommended Installation</summary>

```
curl -fsSL https://raw.githubusercontent.com/jbenshetler/mcp-ragex/refs/heads/main/install.sh | bash
ragex register claude --global # let Claude Code know about this MCP server
cd <project>
ragex start
```

</details>




### Administration
#### Index Catalog

<details>
<summary>Available indices can be catalogued using `ragex ls [-lh]`</summary>

```
PROJECT NAME          PROJECT ID                      MODEL       INDEXED   SYMBOLS   SIZE          PATH
--------------------------------------------------------------------------------------------------------
mcp-ragex             ragex_1000_f8902326ad894225     fast        yes       2624      36.2M         /home/jeff/clients/mcp-ragex
mcp-ragex-example     ragex_1000_de615df33aa15e6f     fast        yes       2606      36.7M         /home/jeff/clients/mcp-ragex-example
nancyknows-web        ragex_1000_787f160eb1a1840a     fast        yes       11759     72.3M         /home/jeff/clients/nancyknows/nancyknows-web
```
</details>



## Improvements
1. Layered Docker images for faster builds.
1. Progress bars while indexing.
1. Support for remote embedding computation. 
1. Download non-default model during installation, to avoid the need for network access during runtime.  
1. Improve test coverage.
1. 

## References
1. "Context Rot: How Increasing Input Tokens Impacts LLM Performance" by Kelly Hong, Anton Troynikov, and Jeff Huber, https://research.trychroma.com/context-rot
1. Claude Code Release Notes, https://claudelog.com/faqs/claude-code-release-notes/
1. "Efficient and robust approximate nearest neighbor search using Hierarchical Navigable Small World graphs", Yu. A. Malkov, D. A. Yashunin, https://arxiv.org/abs/1603.09320