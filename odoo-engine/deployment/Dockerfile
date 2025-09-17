# -----------------------------------------------------------------------------
# Dockerfile for the Odoo Engine Service (mirrors Product Engine deployment)
# -----------------------------------------------------------------------------

FROM python:3.13-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"
RUN poetry config virtualenvs.in-project true

# Copy dependency files first (for better cache)
WORKDIR /app
COPY pyproject.toml poetry.lock* ./

# Install dependencies (cached layer)
RUN poetry install --only main --no-root

# Final stage
FROM python:3.13-slim

# Runtime deps
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY src /app/src

# Set ownership
RUN chown -R appuser:appuser /app

# Set working directory and user
WORKDIR /app
USER appuser

# Activate virtual environment
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src:$PYTHONPATH"

# Default command
CMD ["python", "-m", "odoo_engine.main"]

