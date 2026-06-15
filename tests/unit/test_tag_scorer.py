from src.services.confidence.tag_scorer import (
    TagAssignmentScorer,
    TagType,
)


def test_cached_tag_assignments_are_isolated_from_callers():
    scorer = TagAssignmentScorer()
    content = "memory mcp vector bug fix"
    context = {"agent_id": "codex", "timestamp": "2026-06-15T00:00:00Z"}

    first = scorer.assign_tags(content, context)
    first[TagType.WHO].value = "mutated"
    first[TagType.PROJECT].components["direct_match"] = 0.0

    second = scorer.assign_tags(content, context)

    assert second is not first
    assert second[TagType.WHO] is not first[TagType.WHO]
    assert second[TagType.WHO].value == "codex"
    assert second[TagType.PROJECT].components.get("direct_match") != 0.0


def test_cache_key_uses_full_content_not_prefix_only():
    scorer = TagAssignmentScorer()
    prefix = "x" * 300
    memory_content = prefix + " memory mcp chromadb vector hipporag"
    trading_content = prefix + " trader trading momentum market"

    memory_tags = scorer.assign_tags(memory_content)
    trading_tags = scorer.assign_tags(trading_content)

    assert memory_tags[TagType.PROJECT].value == "memory-mcp-triple-system"
    assert trading_tags[TagType.PROJECT].value == "trader-ai"


def test_cache_key_includes_context_that_changes_assignments():
    scorer = TagAssignmentScorer()
    content = "same content for both calls"

    first = scorer.assign_tags(content, {"agent_id": "codex"})
    second = scorer.assign_tags(content, {"agent_id": "claude"})

    assert first[TagType.WHO].value == "codex"
    assert second[TagType.WHO].value == "claude"
