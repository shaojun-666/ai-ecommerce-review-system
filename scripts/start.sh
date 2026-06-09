#!/bin/bash
# Start development environment
set -e

echo "=== AI E-commerce Review Analysis System ==="
echo "Starting development environment..."

# Check prerequisites
command -v docker >/dev/null 2>&1 || { echo "Docker is required but not installed."; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "Docker Compose is required but not installed."; exit 1; }

# Check for .env file
if [ ! -f ".env" ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "Please update .env with your configuration."
fi

# Create necessary directories
mkdir -p logs
mkdir -p nlp/data/models
mkdir -p nlp/data/raw
mkdir -p nlp/data/processed

# Start services
echo "Starting Docker Compose services..."
docker-compose up -d

echo ""
echo "Services starting:"
echo "  - Frontend:  http://localhost:80"
echo "  - Backend:   http://localhost:8000"
echo "  - API Docs:  http://localhost:8000/health"
echo "  - PostgreSQL: localhost:5432"
echo "  - Redis:      localhost:6379"
echo ""
echo "Run 'docker-compose logs -f' to follow logs."
