#!/bin/bash
set -e

# Run database migrations unless SKIP_MIGRATIONS is set
if [ "$SKIP_MIGRATIONS" != "true" ]; then
    echo "Running database migrations..."
    flask db upgrade
    echo "Migrations complete."
fi

# Execute the main command
exec "$@"
