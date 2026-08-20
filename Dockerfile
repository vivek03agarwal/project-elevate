# Multi-stage secure Python container for Cloud Run
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project definition
COPY pyproject.toml .

# Install dependencies into virtual environment
RUN uv venv /opt/venv && \
    . /opt/venv/bin/activate && \
    uv pip install \
      google-adk \
      google-cloud-discoveryengine \
      google-cloud-storage \
      python-dotenv \
      pyyaml \
      pypdf \
      absl-py \
      fastapi \
      uvicorn \
      pydantic

# Runtime stage
FROM python:3.11-slim AS runtime

WORKDIR /app

# Create non-root app user for security
RUN useradd -m -u 1000 appuser

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source code and knowledge bundle
COPY agent/ /app/agent/
COPY knowledge/ /app/knowledge/
COPY data/ /app/data/
COPY app/ /app/app/

# Set environment defaults
ENV PORT=8080 \
    PYTHONUNBUFFERED=1 \
    RETRIEVAL_MODE=okf \
    GOOGLE_GENAI_USE_VERTEXAI=true \
    GOOGLE_CLOUD_LOCATION=global

# Set non-root ownership
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

# Run FastAPI server via Uvicorn
CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8080"]
