FROM python:3.11-slim

LABEL maintainer="Trend Analysis Team"
LABEL description="Consumer Trend Analysis Multi-Agent System"

# Set working directory
WORKDIR /app

# Install system dependencies including Node.js for MCP servers
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first (for better caching)
COPY requirements.txt pyproject.toml ./

# Install Python dependencies
# Use requirements.txt for explicit version control in Docker
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY config/ ./config/
COPY main.py ./

# Create necessary directories
RUN mkdir -p /app/artifacts/news_trend_agent && \
    mkdir -p /app/artifacts/viral_video_agent && \
    mkdir -p /app/artifacts/social_trend_agent && \
    mkdir -p /app/logs

# Download NLTK data for sentiment analysis
RUN python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab'); nltk.download('averaged_perceptron_tagger'); nltk.download('averaged_perceptron_tagger_eng'); nltk.download('wordnet')"

# Set Python path
ENV PYTHONPATH=/app

# Expose port for FastAPI
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Default command - run API server
CMD ["uvicorn", "src.api.routes.dashboard:app", "--host", "0.0.0.0", "--port", "8000"]
