-- Migration 007: Query Traces Table
-- Week 7: Context Assembly Debugger Foundation
-- Created: 2025-10-18
-- Purpose: 100% query logging for deterministic replay and error attribution

-- Create migrations table if it doesn't exist (MUST BE FIRST!)
CREATE TABLE IF NOT EXISTS migrations (
    version TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Query traces table (30-day retention)
CREATE TABLE IF NOT EXISTS query_traces (
    query_id TEXT PRIMARY KEY,
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    query TEXT NOT NULL,
    user_context TEXT NOT NULL,
    mode_detected TEXT,
    mode_confidence REAL,
    mode_detection_ms INTEGER,
    stores_queried TEXT,
    routing_logic TEXT,
    retrieved_chunks TEXT,
    retrieval_ms INTEGER,
    verification_result TEXT,
    verification_ms INTEGER,
    output TEXT,
    total_latency_ms INTEGER,
    error TEXT,
    error_type TEXT
);

CREATE INDEX IF NOT EXISTS idx_query_traces_timestamp ON query_traces(timestamp);
CREATE INDEX IF NOT EXISTS idx_query_traces_error_type ON query_traces(error_type) WHERE error_type IS NOT NULL;

INSERT OR IGNORE INTO migrations (version, description, applied_at)
VALUES ('007', 'Query traces table for context debugger', datetime('now'));
