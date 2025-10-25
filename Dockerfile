FROM python:3.11-slim

LABEL maintainer="Trend Analysis Team"
LABEL description="Consumer Trend Analysis Multi-Agent System"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Copy application code
COPY agents/ ./agents/
COPY backend/ ./backend/
COPY scripts/ ./scripts/
COPY automation/ ./automation/

# Create necessary directories
RUN mkdir -p /app/artifacts/news_trend_agent && \
    mkdir -p /app/artifacts/viral_video_agent && \
    mkdir -p /app/logs

# Expose port for FastAPI (optional - for future API server)
EXPOSE 8000

# Default command - run news agent with sample query
CMD ["python", "-m", "agents.news_trend_agent", "--query", "AI trends", "--time-window", "7d"]
