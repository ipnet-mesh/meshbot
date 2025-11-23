# Minimal Alpine-based Dockerfile for MeshBot
FROM python:3.11-alpine

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

# Run as non-root user for security
RUN adduser -D -u 1000 meshbot
USER meshbot

# Default command (can be overridden)
ENTRYPOINT ["meshbot"]
CMD ["run", "--meshcore-type", "mock"]

LABEL org.opencontainers.image.source="https://github.com/ipnet-mesh/meshbot"
LABEL org.opencontainers.image.description="AI agent for MeshCore network communication"
LABEL org.opencontainers.image.authors="IPNet Mesh <info@ipnt.uk>"
LABEL org.opencontainers.image.url="https://github.com/ipnet-mesh/meshbot"
LABEL org.opencontainers.image.licenses="GPL-3.0-or-later"
