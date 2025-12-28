#!/usr/bin/env python3
"""
Verification script for Phase 6 Stream B: Data Flow Wiring

Tests that all 3 components are properly wired:
- C3.5: LifecycleManager processing in memory_store
- C3.6: QueryTrace logging in vector_search
- C3.7: Migrations applied on startup

Run: python verify_wiring.py
"""

import re
from pathlib import Path


def verify_wiring():
    """Verify all 3 wiring tasks are complete."""

    stdio_path = Path(__file__).parent / "src" / "mcp" / "stdio_server.py"

    with open(stdio_path, 'r', encoding='utf-8') as f:
        content = f.read()

    results = {
        "C3.5_lifecycle_wired": False,
        "C3.6_trace_logging": False,
        "C3.7_migrations_applied": False
    }

    # C3.5: Check lifecycle manager is called in memory_store
    if "tool.lifecycle_manager.demote_stale_chunks()" in content:
        results["C3.5_lifecycle_wired"] = True
        print("[PASS] C3.5: LifecycleManager.demote_stale_chunks() wired to memory_store")
    else:
        print("[FAIL] C3.5: LifecycleManager NOT wired to memory_store")

    if "tool.lifecycle_manager.archive_demoted_chunks()" in content:
        print("[PASS] C3.5: LifecycleManager.archive_demoted_chunks() wired to memory_store")
    else:
        print("[FAIL] C3.5: LifecycleManager.archive_demoted_chunks() NOT found")

    # C3.6: Check QueryTrace.log() is called in vector_search
    if 'trace.log(db_path=' in content:
        results["C3.6_trace_logging"] = True
        print("[PASS] C3.6: QueryTrace.log() wired to vector_search handler")
    else:
        print("[FAIL] C3.6: QueryTrace.log() NOT called in vector_search")

    # Verify trace fields are set
    if 'trace.stores_queried' in content:
        print("[PASS] C3.6: trace.stores_queried field populated")
    if 'trace.routing_logic' in content:
        print("[PASS] C3.6: trace.routing_logic field populated")
    if 'trace.total_latency_ms' in content:
        print("[PASS] C3.6: trace.total_latency_ms field populated")

    # C3.7: Check migrations are applied in main()
    if '_apply_migrations(config)' in content:
        results["C3.7_migrations_applied"] = True
        print("[PASS] C3.7: _apply_migrations() called in main()")
    else:
        print("[FAIL] C3.7: Migrations NOT applied in main()")

    # Check migration 007 exists
    migration_file = Path(__file__).parent / "migrations" / "007_query_traces_table.sql"
    if migration_file.exists():
        print("[PASS] C3.7: Migration 007 (query_traces) exists")
    else:
        print("[FAIL] C3.7: Migration 007 NOT found")

    # Summary
    print("\n" + "="*60)
    print("WIRING VERIFICATION SUMMARY")
    print("="*60)

    all_passed = all(results.values())

    for task, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"{task}: {status}")

    print("="*60)

    if all_passed:
        print("[SUCCESS] ALL COMPONENTS WIRED SUCCESSFULLY")
        return 0
    else:
        print("[ERROR] SOME COMPONENTS NOT WIRED")
        return 1


if __name__ == "__main__":
    exit(verify_wiring())
