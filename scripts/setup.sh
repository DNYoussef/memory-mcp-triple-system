#!/bin/bash
# Memory MCP Triple System - One-Command Setup Script
# Usage: ./scripts/setup.sh

set -e  # Exit on error

echo "=================================="
echo "Memory MCP Triple System - Setup"
echo "=================================="
echo ""

# Check prerequisites
command -v docker >/dev/null 2>&1 || { echo "Error: Docker is not installed. Please install Docker Desktop."; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "Error: Docker Compose is not installed."; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "Error: Python 3.11+ is not installed."; exit 1; }

echo "✓ Prerequisites check passed"
echo ""

# Create .env file from template
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✓ .env file created (please update with your values)"
    echo ""
else
    echo "✓ .env file already exists"
    echo ""
fi

# Create Obsidian vault directory
VAULT_PATH="${HOME}/Documents/Memory-Vault"
if [ ! -d "${VAULT_PATH}" ]; then
    echo "Creating Obsidian vault at ${VAULT_PATH}..."
    mkdir -p "${VAULT_PATH}"
    mkdir -p "${VAULT_PATH}/People"
    mkdir -p "${VAULT_PATH}/Projects"
    mkdir -p "${VAULT_PATH}/Notes"
    mkdir -p "${VAULT_PATH}/Journal"
    echo "✓ Obsidian vault created"
    echo ""
else
    echo "✓ Obsidian vault already exists"
    echo ""
fi

# Pull Docker images
echo "Pulling Docker images (this may take a few minutes)..."
docker-compose pull
echo "✓ Docker images pulled"
echo ""

# Start Docker services
echo "Starting Docker services..."
docker-compose up -d
echo "✓ Docker services started"
echo ""

# Wait for services to be healthy
echo "Waiting for services to be ready..."
sleep 10

# Check service health
echo "Checking service health..."
docker-compose ps

# Verify Qdrant
if curl -sf http://localhost:6333/healthz > /dev/null; then
    echo "✓ Qdrant is healthy (http://localhost:6333)"
else
    echo "⚠ Warning: Qdrant may not be ready yet"
fi

# Verify Neo4j
if curl -sf http://localhost:7474 > /dev/null; then
    echo "✓ Neo4j is healthy (http://localhost:7474)"
else
    echo "⚠ Warning: Neo4j may not be ready yet"
fi

# Verify Redis
if docker exec memory-mcp-redis redis-cli ping | grep -q PONG; then
    echo "✓ Redis is healthy (localhost:6379)"
else
    echo "⚠ Warning: Redis may not be ready yet"
fi

echo ""
echo "=================================="
echo "Setup Complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "1. Install Python dependencies: pip install -r requirements.txt"
echo "2. Install spaCy model: python -m spacy download en_core_web_trf"
echo "3. Update .env file with your configuration"
echo "4. Run tests: pytest"
echo "5. Start MCP server: python -m src.mcp.server"
echo ""
echo "Services:"
echo "- Qdrant: http://localhost:6333"
echo "- Neo4j: http://localhost:7474 (user: neo4j, pass: memory-mcp-password)"
echo "- Redis: localhost:6379"
echo ""
echo "To stop services: docker-compose down"
echo "To view logs: docker-compose logs -f"
echo ""
