# Week 1, Task 1: Docker Compose Setup

**Assigned To**: backend-dev Drone
**Priority**: P0 (Blocking Week 1 milestone)
**Estimated Time**: 4 hours
**Loop**: Loop 2 (Implementation)

## Objective

Create a production-ready Docker Compose setup for the Memory MCP Triple System with:
- Qdrant (vector database)
- Neo4j (graph database)
- Redis (caching)
- Health checks
- Volume management

## Requirements (From SPEC v4.0)

**FR-77**: Embedded Qdrant mode (optional, for simpler setups)
**FR-84**: Consolidated MCP Server (all-in-one container)
**FR-93**: CI/CD pipeline (GitHub Actions, automated deploy)
**FR-98**: Pre-built Docker images (Docker Hub, instant pull)

## Deliverables

1. **docker-compose.yml** (services: qdrant, neo4j, redis)
   - Qdrant: Port 6333, volume ./data/qdrant
   - Neo4j: Port 7687 (bolt), 7474 (HTTP), volume ./data/neo4j
   - Redis: Port 6379, volume ./data/redis
   - Health checks for all services
   - Restart policies (unless-stopped)
   - Network: memory-mcp-network

2. **Dockerfile.mcp-server** (MCP server + file watcher + web UI)
   - Python 3.11
   - Install dependencies (sentence-transformers, qdrant-client, neo4j, fastapi)
   - Copy src/ directory
   - Expose port 8080
   - CMD: Run MCP server

3. **scripts/setup.sh** (one-command setup)
   - Check Docker/Docker Compose installed
   - Create data directories
   - Pull/build images
   - Start containers
   - Health check validation
   - Print success message with URLs

4. **.github/workflows/ci.yml** (basic CI pipeline)
   - On push/PR: Run tests
   - On merge to main: Build Docker images
   - On release: Tag and push to Docker Hub

## Acceptance Criteria

- [ ] `docker-compose up` starts all 3 services successfully
- [ ] Health checks pass for all services (Qdrant, Neo4j, Redis)
- [ ] Qdrant accessible at http://localhost:6333
- [ ] Neo4j accessible at bolt://localhost:7687
- [ ] Redis accessible at localhost:6379
- [ ] `scripts/setup.sh` completes in <5 minutes (first run)
- [ ] Data persists across container restarts (volumes working)
- [ ] No hardcoded secrets (use .env file)

## Technical Constraints

**NASA Rule 10**: ≤60 LOC per function in setup scripts
**Performance**: Startup time <30 seconds (after images pulled)
**Security**: No root user in containers, secrets from environment

## Dependencies

- Docker 24.0+
- Docker Compose 2.0+
- .env file (from .env.example)

## Testing Plan

```bash
# Test 1: Setup script works
./scripts/setup.sh

# Test 2: All services healthy
docker-compose ps  # All should show "healthy"

# Test 3: Qdrant accessible
curl http://localhost:6333/health  # Should return 200

# Test 4: Neo4j accessible
docker exec memory-mcp-neo4j cypher-shell -u neo4j -p $NEO4J_PASSWORD "RETURN 1"

# Test 5: Redis accessible
docker exec memory-mcp-redis redis-cli ping  # Should return PONG

# Test 6: Data persistence
docker-compose down && docker-compose up -d
# Data should still be there
```

## Files to Create

1. `docker-compose.yml` (root)
2. `Dockerfile.mcp-server` (root)
3. `scripts/setup.sh` (scripts/)
4. `.github/workflows/ci.yml` (.github/workflows/)
5. `scripts/health-check.sh` (scripts/)

## References

- SPEC v4.0: FR-77, FR-84, FR-93, FR-98
- Loop 1 Implementation Plan: Week 1 (Docker setup)
- Config: config/memory-mcp.yaml

## Notes

- Use official Docker images where possible (qdrant/qdrant, neo4j, redis)
- Bundle Sentence-Transformers model in MCP server image (no download at runtime)
- Setup script should be idempotent (can run multiple times safely)

---

**Status**: Ready for implementation
**Created**: 2025-10-17
**Princess-Dev**: Coordinating
