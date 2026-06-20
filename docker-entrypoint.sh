#!/bin/bash
set -e

# If .env doesn't exist, copy from .env.example
if [ ! -f /app/.env ]; then
    echo "Creating .env from .env.example..."
    cp /app/.env.example /app/.env
    echo "✓ .env created with placeholder values"
    echo ""
    echo "⚠️  IMPORTANT: Add your OPENAI_API_KEY to .env"
    echo "   Without it, the agent will not be able to process requests."
    echo ""
fi

# Load .env into environment for this process and children
set -a
[ -f /app/.env ] && . /app/.env
set +a

# Execute the original command
exec "$@"
