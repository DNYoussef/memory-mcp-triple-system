"""Regression tests for namespace key construction (MECE H8)."""

from src.telemetry.namespace_router import (
    TelemetryNamespace,
    build_namespace_key,
    parse_namespace_key,
)


class TestBuildNamespaceKeyMissingSegments:
    def test_missing_middle_segment_does_not_drop_later_segments(self):
        """Missing optional segments keep a placeholder so later fields survive."""
        key = build_namespace_key(
            TelemetryNamespace.AGENTS,
            category="coder",
            project="memory-mcp",
            timestamp="2026-06-15T00:00:00Z",
        )

        assert key == "agents:coder::memory-mcp:2026-06-15T00:00:00Z"

    def test_trailing_missing_segments_stay_compact(self):
        """Only interior gaps need placeholders; trailing missing segments stay omitted."""
        key = build_namespace_key(
            TelemetryNamespace.AGENTS,
            category="coder",
        )

        assert key == "agents:coder"

    def test_parse_sparse_key_preserves_later_segment_names(self):
        """A sparse key should round-trip through the builder without shifting names."""
        key = build_namespace_key(
            TelemetryNamespace.FINDINGS,
            agent="reviewer",
            id="finding-123",
        )

        parsed = parse_namespace_key(key)

        assert parsed is not None
        assert parsed.segments == {
            "agent": "reviewer",
            "id": "finding-123",
        }
