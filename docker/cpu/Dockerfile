# Stage 1: Builder
FROM python:3.10-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy dependency files
COPY requirements/ ./requirements/
COPY pyproject.toml ./

# Install Python dependencies (CPU-only versions)
RUN pip install --user --no-cache-dir -r requirements/cpu.txt

# Stage 2: Runtime
FROM python:3.10-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    git \
    ripgrep \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 ragex

WORKDIR /app

# Copy dependencies from builder
COPY --from=builder /root/.local /home/ragex/.local
ENV PATH=/home/ragex/.local/bin:$PATH

# Copy application code
COPY --chown=ragex:ragex src/ ./src/
COPY --chown=ragex:ragex scripts/ ./scripts/
COPY --chown=ragex:ragex pyproject.toml ./
COPY --chown=ragex:ragex ragex_search.py ./

# Create data directories
RUN mkdir -p /data/chroma_db /data/models && \
    chown -R ragex:ragex /data

# Switch to non-root user
USER ragex

# Pre-download tree-sitter language parsers (after switching to user with Python packages)
RUN python -c "import tree_sitter; import tree_sitter_python as tspython; import tree_sitter_javascript as tsjavascript; import tree_sitter_typescript as tstypescript"

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV RAGEX_DATA_DIR=/data
ENV HF_HOME=/data/models
ENV SENTENCE_TRANSFORMERS_HOME=/data/models
ENV DOCKER_CONTAINER=true
ENV RAGEX_LOG_LEVEL=INFO
# Force CPU-only mode for PyTorch
ENV CUDA_VISIBLE_DEVICES=""

# Copy and set entrypoint
COPY --chown=ragex:ragex docker/common/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]