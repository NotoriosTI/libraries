#!/bin/bash

# ==============================================================================
# connect_db.sh
#
# Description:
#   Connects to the PostgreSQL database through the running Cloud SQL Auth Proxy
#   using the psql client.
#
# Pre-requisites:
#   - The psql client is installed.
#   - The start_proxy.sh script is running in another terminal.
#
# Usage:
#   To connect to the default database ('salesdb'):
#   ./connect_db.sh
#
#   To connect to a specific database:
#   ./connect_db.sh your_other_db_name
#
# ==============================================================================

# --- Configuration ---
DB_USER="automation_admin"
DB_HOST="127.0.0.1"
DB_PORT="5432"

# --- Logic ---
# Set the database name.
# It uses the first command-line argument ($1).
# If no argument is provided, it defaults to 'salesdb'.
DB_NAME=${1:-salesdb}

echo "Connecting to database '$DB_NAME' as user '$DB_USER'..."

# --- Connect with psql ---
# The script will now hand over control to psql.
# You will be prompted for the password for the DB_USER.
psql --host=$DB_HOST --port=$DB_PORT --username=$DB_USER --dbname=$DB_NAME

