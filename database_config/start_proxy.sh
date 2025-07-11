#!/bin/bash

# ==============================================================================
# start_proxy.sh
#
# Description:
#   This script starts the Cloud SQL Auth Proxy to connect to a specific
#   Google Cloud SQL PostgreSQL instance.
#
# Pre-requisites:
#   - Google Cloud SDK (gcloud) is installed and authenticated.
#   - The Cloud SQL Auth Proxy executable is in the same directory or in the PATH.
#   - The user running the script has the "Cloud SQL Client" IAM role.
#
# Usage:
#   ./start_proxy.sh
#
#   It's recommended to run this in the background:
#   ./start_proxy.sh &
#
# ==============================================================================

# --- Configuration ---
# !!! IMPORTANT !!!
# Replace 'your-gcp-project-id:your-region' with your actual GCP project ID
# and the region of your SQL instance.
# You can find the full connection name on your instance's page in the
# Google Cloud Console or by running:
# gcloud sql instances describe app-temp --format='value(connectionName)'

INSTANCE_CONNECTION_NAME="notorios:us-central1:app-temp"

# The port the proxy will listen on for PostgreSQL connections.
# 5432 is the default for PostgreSQL.
PORT=5432

echo "Starting Cloud SQL Auth Proxy for instance: $INSTANCE_CONNECTION_NAME"
echo "Proxy will listen on 127.0.0.1:$PORT"
echo "Press Ctrl+C to exit."

# --- Start Proxy ---
# The command will run in the foreground. If you want it to run in the
# background, add an ampersand (&) to the end of the command or run the

# script with './start_proxy.sh &'
cloud-sql-proxy --port=$PORT $INSTANCE_CONNECTION_NAME
