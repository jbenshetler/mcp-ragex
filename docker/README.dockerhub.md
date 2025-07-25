# MCP-RageX

Intelligent code search server for Claude and AI assistants using RAG, tree-sitter, and ripgrep.

## Quick Start

```bash
# Pull the image
docker pull mcp-ragex/mcp-server:latest

# Run the server
docker run -it -v $(pwd):/workspace:ro mcp-ragex/mcp-server

# With semantic search
docker run -it -v $(pwd):/workspace:ro -v ragex-data:/data mcp-ragex/mcp-server
```

## Features

- 🔍 **Intelligent Search**: Semantic, symbol, and regex search modes
- 🚀 **Fast**: Ripgrep-powered with caching
- 🔒 **Secure**: Input validation and sandboxing
- 🌳 **Language Aware**: Tree-sitter parsing
- 🧠 **AI-Powered**: Sentence transformer embeddings

## Supported Platforms

- `linux/amd64` (Intel/AMD 64-bit)
- `linux/arm64` (Apple Silicon, ARM 64-bit)

## Documentation

Full documentation available at: https://github.com/YOUR_USERNAME/mcp-ragex

## License

MIT