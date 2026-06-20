#!/bin/bash
set -e

# If OPENAI_API_KEY is not already set from environment (passed by docker-compose),
# then create .env from .env.example
if [ -z "$OPENAI_API_KEY" ]; then
    echo "Creating .env from .env.example..."
    cp /app/.env.example /app/.env
    echo "✓ .env created with placeholder values"
    echo ""
    echo "⚠️  IMPORTANT: Add your OPENAI_API_KEY to .env"
    echo "   Without it, the agent will not be able to process requests."
    echo ""

    # Load .env into environment for this process and children
    set -a
    [ -f /app/.env ] && . /app/.env
    set +a
else
    echo "✓ Using environment variables passed from docker-compose"
fi

# Execute the original command
exec "$@"
