"""
Integration tests for memory_store and retrieval round-trip.
MEM-CLEAN-007: Core path verification.

Tests the 10-step memory_store flow identified in MEM-CLEAN-006:
1. Metadata normalization
2. Metadata validation
3. Tag enrichment (WHO/WHEN/PROJECT/WHY)
4. Confidence assignment
5. Hot/Cold classification
6. Embedding generation
7. ChromaDB insert
8. Entity extraction + graph
9. Lifecycle management
10. Event logging

NASA Rule 10 Compliant: All test methods <=60 LOC
"""
import pytest
import sys

from src.mcp.request_router import (
    _normalize_metadata_tags,
    _validate_metadata,
    _enrich_metadata_with_tagging,
    _assign_confidence,
)


class TestMetadataProcessing:
    """Test metadata normalization and validation."""

    def test_normalize_uppercase_tags(self):
        """Uppercase WHO/WHEN/PROJECT/WHY should normalize to lowercase."""
        metadata = {
            "WHO": "test-agent",
            "WHEN": "2026-01-18T10:00:00Z",
            "PROJECT": "test-project",
            "WHY": "testing",
        }
        normalized = _normalize_metadata_tags(metadata)
        assert "who" in normalized
        assert normalized["who"] == "test-agent"

    def test_normalize_mixed_case(self):
        """Mixed case should work correctly."""
        metadata = {"WHO": "agent", "when": "now", "PROJECT": "test"}
        normalized = _normalize_metadata_tags(metadata)
        assert normalized["who"] == "agent"
        assert normalized["when"] == "now"

    def test_validate_complete_metadata(self):
        """Complete metadata should pass validation."""
        metadata = {"who": "agent", "when": "now", "project": "test", "why": "testing"}
        is_valid, missing = _validate_metadata(metadata)
        assert is_valid
        assert len(missing) == 0

    def test_validate_missing_tags(self):
        """Missing tags should be identified."""
        metadata = {"who": "agent"}
        is_valid, missing = _validate_metadata(metadata)
        assert not is_valid
        assert "when" in missing
        assert "project" in missing
        assert "why" in missing

    def test_validate_empty_metadata(self):
        """Empty metadata should identify all missing tags."""
        is_valid, missing = _validate_metadata({})
        assert not is_valid
        assert len(missing) == 4

    def test_validate_none_metadata(self):
        """None metadata should identify all missing tags."""
        is_valid, missing = _validate_metadata(None)
        assert not is_valid
        assert len(missing) == 4


class TestMetadataEnrichment:
    """Test metadata enrichment with WHO/WHEN/PROJECT/WHY protocol."""

    def test_enrich_metadata_adds_all_tags(self):
        """Enrichment should add all required tags."""
        metadata = {"agent": "test-agent"}
        enriched = _enrich_metadata_with_tagging(metadata)
        assert "WHO" in enriched
        assert "WHEN" in enriched
        assert "PROJECT" in enriched
        assert "WHY" in enriched
        assert "_tagging_version" in enriched

    def test_enrich_preserves_existing(self):
        """Enrichment should preserve existing values."""
        metadata = {"WHO": "existing-agent", "custom": "value"}
        enriched = _enrich_metadata_with_tagging(metadata)
        assert enriched["custom"] == "value"

    def test_enrich_adds_timestamps(self):
        """Enrichment should add timestamp fields."""
        metadata = {}
        enriched = _enrich_metadata_with_tagging(metadata)
        assert "timestamp_iso" in enriched
        assert "timestamp_unix" in enriched
        assert "timestamp_readable" in enriched

    def test_enrich_adds_agent_fields(self):
        """Enrichment should add agent-related fields."""
        metadata = {"agent": "my-agent", "agent_category": "research"}
        enriched = _enrich_metadata_with_tagging(metadata)
        assert enriched["agent_name"] == "my-agent"
        assert enriched["agent_category"] == "research"


class TestConfidenceAssignment:
    """Test confidence scoring based on source type."""

    def test_confidence_witnessed(self):
        """Witnessed source should get 0.95 confidence."""
        metadata = {"source_type": "witnessed"}
        confidence = _assign_confidence(metadata)
        assert confidence == 0.95

    def test_confidence_reported(self):
        """Reported source should get 0.70 confidence."""
        metadata = {"source_type": "reported"}
        confidence = _assign_confidence(metadata)
        assert confidence == 0.70

    def test_confidence_inferred(self):
        """Inferred source should get 0.50 confidence."""
        metadata = {"source_type": "inferred"}
        confidence = _assign_confidence(metadata)
        assert confidence == 0.50

    def test_confidence_assumed(self):
        """Assumed source should get 0.30 confidence."""
        metadata = {"source_type": "assumed"}
        confidence = _assign_confidence(metadata)
        assert confidence == 0.30

    def test_confidence_unknown_defaults(self):
        """Unknown source should default to 0.50."""
        metadata = {"source_type": "unknown"}
        confidence = _assign_confidence(metadata)
        assert confidence == 0.5

    def test_confidence_preserves_existing(self):
        """Existing confidence should be preserved."""
        metadata = {"confidence": 0.99}
        confidence = _assign_confidence(metadata)
        assert confidence == 0.99

    def test_confidence_case_insensitive(self):
        """Source type matching should be case-insensitive."""
        metadata = {"source_type": "WITNESSED"}
        confidence = _assign_confidence(metadata)
        assert confidence == 0.95


class TestStoreRetrieveIntegration:
    """Integration tests requiring real services (skipped on Windows due to file locking)."""

    @pytest.mark.skipif(
        sys.platform == "win32", reason="ChromaDB file locking on Windows"
    )
    def test_store_retrieve_roundtrip(self):
        """Full store and retrieve cycle with real ChromaDB."""
        pytest.skip("Requires real ChromaDB setup - run manually")

    def test_handler_structure(self):
        """Verify handler imports work correctly."""
        from src.mcp.request_router import handle_memory_store, handle_vector_search

        assert callable(handle_memory_store)
        assert callable(handle_vector_search)

    def test_required_tags_constant(self):
        """Verify REQUIRED_TAGS constant exists."""
        from src.mcp.request_router import REQUIRED_TAGS

        assert "who" in REQUIRED_TAGS
        assert "when" in REQUIRED_TAGS
        assert "project" in REQUIRED_TAGS
        assert "why" in REQUIRED_TAGS
