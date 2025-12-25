# ============================================================================
# Stage 1: Build stage
# ============================================================================
FROM python:3.11-slim AS builder

LABEL maintainer="Trend Analysis Team"
LABEL description="Consumer Trend Analysis Multi-Agent System - Build Stage"

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY requirements.txt pyproject.toml ./

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Download NLTK data
RUN python -c "import nltk; \
    nltk.download('punkt'); \
    nltk.download('punkt_tab'); \
    nltk.download('averaged_perceptron_tagger'); \
    nltk.download('averaged_perceptron_tagger_eng'); \
    nltk.download('wordnet'); \
    nltk.download('stopwords')"

# ============================================================================
# Stage 2: Runtime stage
# ============================================================================
FROM python:3.11-slim

LABEL maintainer="Trend Analysis Team"
LABEL description="Consumer Trend Analysis Multi-Agent System - Runtime"

WORKDIR /app

# Install only runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy NLTK data
COPY --from=builder /root/nltk_data /root/nltk_data

# Copy application code
COPY src/ ./src/
COPY config/ ./config/
COPY main.py ./

# Create necessary directories
RUN mkdir -p /app/artifacts/news_trend_agent \
             /app/artifacts/viral_video_agent \
             /app/artifacts/social_trend_agent \
             /app/logs && \
    chmod -R 755 /app/artifacts /app/logs

# Set Python path
ENV PYTHONPATH=/app

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port for FastAPI
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Default command - run API server
CMD ["uvicorn", "src.api.routes.dashboard:app", "--host", "0.0.0.0", "--port", "8000"]
