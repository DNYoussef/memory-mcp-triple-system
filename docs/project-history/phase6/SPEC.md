# Phase 6: Production Hardening - Specification

## Overview

Complete runtime wiring, enable all production features, and prepare for deployment.

## Remaining Issues (6 total)

### C3.* Runtime Wiring Gaps

1. **C3.2 - ObsidianClient Never Imported**
   - Evidence: Only tests import ObsidianClient
   - Fix: Wire into stdio_server.py for vault sync

2. **C3.3 - Event Log Never Populated**
   - Evidence: EventLog exists but never called
   - Fix: Add event logging to MCP tool handlers

3. **C3.4 - KV Store Never Used**
   - Evidence: KVStore exists but never called
   - Fix: Use for session state and preferences

4. **C3.5 - Lifecycle Manager Never Invoked**
   - Evidence: LifecycleManager exists but never called
   - Fix: Wire into memory_store handler for decay

5. **C3.6 - QueryTrace.log Never Called**
   - Evidence: QueryTrace.log exists but never called
   - Fix: Add query tracing to search handlers

6. **C3.7 - Migration 007 Not Auto-Applied**
   - Evidence: SQL file exists but not applied
   - Fix: Add migration runner to server startup

### B4.* Data Flow Issues (already partially resolved)

- B4.1-B4.2: Fixed in Phase 1 (collection name alignment)
- B4.3: NetworkBuilder only in tests (acceptable - lazy init)
- B4.4: HotColdClassifier only in tests (wire to lifecycle manager)

## Implementation Plan

### Step 1: Wire ObsidianClient (C3.2)
- Import ObsidianClient in stdio_server.py
- Add sync_vault MCP tool or startup sync

### Step 2: Enable Event Logging (C3.3)
- Initialize EventLog in stdio_server.py
- Log tool calls in handle_call_tool

### Step 3: Enable KV Store (C3.4)
- Initialize KVStore for session preferences
- Use in memory_store for caching

### Step 4: Wire Lifecycle Manager (C3.5)
- Initialize LifecycleManager with HotColdClassifier
- Call on memory_store to classify memories

### Step 5: Enable Query Tracing (C3.6)
- Create traces in search handlers
- Log to database for debugging

### Step 6: Auto-Apply Migrations (C3.7)
- Add migration check to server startup
- Apply pending migrations automatically

## Success Criteria

1. All 6 runtime wiring issues resolved
2. Production config validated
3. Performance benchmarks passing
4. Monitoring hooks in place
5. Version 1.4.0 released

## Constraints

- Must not break existing MCP protocol
- Must maintain NASA Rule 10 compliance
- Must be backward compatible
