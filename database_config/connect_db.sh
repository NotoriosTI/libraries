#!/bin/bash

# ==============================================================================
# connect_db.sh
#
# Description:
#   Connects to a PostgreSQL database using credentials from a .env file.
#   Uses a connection URI so that password input is skipped.
#
# Pre-requisites:
#   - The psql client is installed.
#   - A .env file exists in the database_config root with:
#       DB_USER=automation_admin
#       DB_PASS=your_password
#       DB_HOST=127.0.0.1
#       DB_PORT=5432
#
# Usage:
#   ./connect_db.sh                # connects to 'juandb'
#   ./connect_db.sh my_database    # connects to 'my_database'
# ==============================================================================

# --- Load environment variables from .env ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

if [ -f "$ENV_FILE" ]; then
  # Export variables defined in .env (ignoring comments and empty lines)
  export $(grep -v '^#' "$ENV_FILE" | xargs)
else
  echo "❌ Error: .env file not found in $SCRIPT_DIR"
  exit 1
fi

# --- Logic ---
DB_NAME=${1:-juandb}

echo "Connecting to database '$DB_NAME' as user '$DB_USER'..."

# --- Connect with psql using connection URI ---
psql "postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
