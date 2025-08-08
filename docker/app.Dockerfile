# Application image for MCP-RAGex
# This lightweight image builds on the base image and adds only the application code

# Allow base image to be specified at build time
ARG BASE_IMAGE=ghcr.io/jbenshetler/mcp-ragex-base:latest
FROM ${BASE_IMAGE}

# Metadata
LABEL org.opencontainers.image.title="MCP-RAGex"
LABEL org.opencontainers.image.description="Intelligent code search server for Claude and AI assistants"
LABEL org.opencontainers.image.authors="jbenshetler"
LABEL org.opencontainers.image.source="https://github.com/jbenshetler/mcp-ragex"
LABEL org.opencontainers.image.licenses="MIT"

# Switch to app directory
WORKDIR /app

# Install jq for JSON processing in shell scripts
USER root
RUN apt-get update && apt-get install -y --no-install-recommends jq && rm -rf /var/lib/apt/lists/*

# Update to newer tree-sitter that has captures() API
# Force upgrade since base image has older versions
RUN pip install --no-cache-dir --upgrade \
    tree-sitter>=0.22.0 \
    tree-sitter-python>=0.23.0 \
    tree-sitter-javascript>=0.23.0 \
    tree-sitter-typescript>=0.23.0

# Install watchdog for file monitoring
RUN pip install --no-cache-dir watchdog>=3.0.0

# Copy application code with correct ownership
COPY --chown=ragex:ragex src/ ./src/
COPY --chown=ragex:ragex scripts/ ./scripts/
COPY --chown=ragex:ragex pyproject.toml ./
COPY --chown=ragex:ragex ragex_search.py ./

# Copy docker entrypoint
COPY --chown=ragex:ragex docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create necessary directories if they don't exist (still as root)
RUN mkdir -p /workspace && chown ragex:ragex /workspace

# Switch to non-root user
USER ragex

# Environment variables
ENV PYTHONPATH=/app
ENV PATH=/home/ragex/.local/bin:$PATH
ENV RAGEX_MODELS_DIR=/data/models
ENV RAGEX_CHROMA_PERSIST_DIR=/data/chroma_db
ENV HF_HOME=/data/models
ENV SENTENCE_TRANSFORMERS_HOME=/data/models
ENV RAGEX_LOG_LEVEL=WARN
ENV RAGEX_IGNOREFILE_WARNING=false

# Data and workspace volumes
VOLUME ["/data", "/workspace"]

# Expose MCP server port (if needed in future)
# EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import src.server; print('OK')" || exit 1

# Default entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Default command - run MCP server
CMD ["serve"]