# Stage 1: Builder
FROM nvidia/cuda:12.1.0-devel-ubuntu22.04 AS builder

# Install Python and build dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3.10-dev \
    python3-pip \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Create symlinks for python
RUN ln -sf /usr/bin/python3.10 /usr/bin/python && \
    ln -sf /usr/bin/python3.10 /usr/bin/python3

WORKDIR /build

# Copy dependency files
COPY requirements/ ./requirements/
COPY pyproject.toml ./

# Install Python dependencies (CUDA versions)
RUN pip install --user --no-cache-dir -r requirements/cuda.txt

# Stage 2: Runtime
FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04

# Install Python and runtime dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    git \
    ripgrep \
    && rm -rf /var/lib/apt/lists/*

# Create symlinks for python
RUN ln -sf /usr/bin/python3.10 /usr/bin/python && \
    ln -sf /usr/bin/python3.10 /usr/bin/python3

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

# Copy and set entrypoint
COPY --chown=ragex:ragex docker/common/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]