# -----------------------------------------------------------------------------
# Dockerfile for the Sales Engine Service (Unified Forecast Table)
# -----------------------------------------------------------------------------
# This Dockerfile uses a multi-stage build to create a lean, production-ready
# container for the sales-engine application with unified forecast table structure.
# It assumes dependencies like 'odoo-api' and 'config-manager' are fetched from Git via pyproject.toml.

# --- Stage 1: Builder ---
# This stage installs Poetry and project dependencies into a virtual environment.
FROM python:3.13-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies required for building Python packages.
# 'git' is essential for fetching dependencies from Git repositories.
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Add Poetry to the PATH
ENV PATH="/root/.local/bin:${PATH}"

# Configure Poetry to create the virtual environment inside the project's directory
# This makes it easy to copy the venv to the next stage
RUN poetry config virtualenvs.in-project true

# Copy only the files needed to install dependencies
# This leverages Docker's layer caching. The install step will only re-run
# if pyproject.toml or poetry.lock changes.
COPY ./pyproject.toml ./poetry.lock ./

# Install dependencies from pyproject.toml.
# Poetry will fetch 'odoo-api' and 'config-manager' from their Git URLs.
# Only install dependencies, not the project itself (--no-root).
RUN poetry install --only main --no-root


# --- Stage 2: Final Production Image ---
# This stage creates the final, lightweight image by copying only the necessary
# application code and the virtual environment from the builder stage.
FROM python:3.13-slim as final

# Set working directory
WORKDIR /app

# Set non-interactive frontend for package installations
ENV DEBIAN_FRONTEND=noninteractive

# Install only necessary production system dependencies.
# 'postgresql-client' is needed for psycopg2 to connect to the database.
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

# Copy the virtual environment from the builder stage
COPY --from=builder /app/.venv ./.venv

# Copy the application source code
# This is done *after* installing dependencies to optimize caching.
COPY ./src ./src

# Activate the virtual environment by adding it to the PATH
ENV PATH="/app/.venv/bin:${PATH}"

# Set environment variables for the application
ENV ENVIRONMENT=production
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app/src:${PYTHONPATH}"

# Change ownership of the app directory to the non-root user
RUN chown -R appuser:appuser /app

# Switch to the non-root user
USER appuser

# Set the default command to run the main entry point
# Since we use --no-root, run the module directly
CMD ["python", "-m", "sales_engine.main"]