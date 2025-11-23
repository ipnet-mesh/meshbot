# Minimal Alpine-based Dockerfile for MeshCore MCP Server
FROM python:3.10-alpine

# Install build dependencies (needed for some Python packages)
RUN apk add --no-cache \
    gcc \
    musl-dev \
    linux-headers \
    && rm -rf /var/cache/apk/*

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml ./
COPY src/ ./src/

# Install the package
RUN pip install --no-cache-dir -e .

# Expose default port
EXPOSE 8000

# Default command (can be overridden)
ENTRYPOINT ["python", "-m", "meshcore_mcp.server"]
CMD ["--host", "0.0.0.0", "--port", "8000"]

LABEL org.opencontainers.image.source="https://github.com/ipnet-mesh/meshcore-mcp"
LABEL org.opencontainers.image.description="MeshCore Companion Node MCP Server"
