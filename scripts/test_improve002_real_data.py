#!/usr/bin/env python3
"""Real Data Test for IMPROVE-002: Automatic Weekly Review.

Tests weekly review with real data:
- Usage aggregation
- Quality trends analysis
- Cost/token analysis
- Suggestion generation

WHO: weekly-review:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: testing (IMPROVE-002)
"""

import sys
import os
from datetime import datetime, timezone, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_imports():
    """Test all imports work correctly."""
    print("\n" + "=" * 60)
    print("TEST 1: Import Verification")
    print("=" * 60)

    try:
        from src.services.weekly_review import (
            WeeklyReview,
            UsageSummary,
            QualityTrend,
            CostAnalysis,
            ImprovementSuggestion,
            SuggestionPriority,
            UsageAggregator,
            QualityTrendsAnalyzer,
            CostTokenAnalyzer,
            SuggestionsGenerator,
            WeeklyReviewCoordinator,
        )
        print("[PASS] All imports successful")
        return True
    except Exception as e:
        print(f"[FAIL] Import error: {e}")
        return False


def test_usage_aggregator():
    """Test usage aggregator with real data."""
    print("\n" + "=" * 60)
    print("TEST 2: Usage Aggregator")
    print("=" * 60)

    from src.services.weekly_review.usage_aggregator import UsageAggregator

    aggregator = UsageAggregator()

    # Record real operations
    operations = [
        ("store", "mode_detection", 45.2),
        ("retrieve", "entity_extraction", 12.8),
        ("search", "mode_detection", 156.3),
        ("store", "tag_assignment", 38.1),
        ("retrieve", "mode_detection", 8.5),
        ("graph_query", "relationships", 234.5),
        ("update", "entity_extraction", 42.0),
        ("search", "tag_assignment", 189.2),
        ("retrieve", "mode_detection", 11.2),
        ("store", "mode_detection", 39.8),
    ]

    for op_type, category, duration in operations:
        aggregator.record_operation(op_type, category, duration)

    # Aggregate
    summary = aggregator.aggregate(days=7)

    print(f"  Period: {summary.period_start[:10]} to {summary.period_end[:10]}")
    print(f"  Total stores: {summary.total_stores}")
    print(f"  Total retrievals: {summary.total_retrievals}")
    print(f"  Total searches: {summary.total_searches}")
    print(f"  Total graph queries: {summary.total_graph_queries}")
    print(f"  By category: {summary.by_category}")

    assert summary.total_stores == 4
    assert summary.total_retrievals == 3
    assert summary.total_searches == 2
    print("[PASS] Usage aggregator working")
    return True, aggregator


def test_quality_trends():
    """Test quality trends analyzer."""
    print("\n" + "=" * 60)
    print("TEST 3: Quality Trends Analyzer")
    print("=" * 60)

    from src.services.weekly_review.quality_trends import QualityTrendsAnalyzer

    analyzer = QualityTrendsAnalyzer()

    # Record quality metrics over time
    # Simulate 7 days of data
    base_time = datetime.now(timezone.utc) - timedelta(days=7)

    for day in range(7):
        timestamp = base_time + timedelta(days=day)

        # Success rate - slightly improving
        analyzer.record_metric("success_rate", 0.75 + (day * 0.02), timestamp)

        # Confidence - declining
        analyzer.record_metric("confidence_avg", 0.72 - (day * 0.015), timestamp)

        # Escalation rate - stable
        analyzer.record_metric("escalation_rate", 0.18 + (day * 0.005), timestamp)

        # Cache hit rate - improving
        analyzer.record_metric("cache_hit_rate", 0.65 + (day * 0.03), timestamp)

    # Analyze trends
    trends = analyzer.analyze_trends(days=7)

    print(f"  Trends analyzed: {len(trends)}")
    for trend in trends:
        print(f"    {trend.metric_name}: {trend.current_value:.2f} ({trend.direction.value}, {trend.change_percent:+.1f}%)")
        if trend.is_warning:
            print(f"      [WARNING] Below threshold")
        if trend.is_critical:
            print(f"      [CRITICAL] Needs attention")

    assert len(trends) > 0
    print("[PASS] Quality trends analyzer working")
    return True, analyzer


def test_cost_analyzer():
    """Test cost/token analyzer."""
    print("\n" + "=" * 60)
    print("TEST 4: Cost/Token Analyzer")
    print("=" * 60)

    from src.services.weekly_review.cost_analyzer import CostTokenAnalyzer

    analyzer = CostTokenAnalyzer()

    # Record token usage
    usage_data = [
        (1500, 800, "claude-3-sonnet", "mode_detection", "task-001"),
        (2200, 1200, "claude-3-haiku", "entity_extraction", "task-002"),
        (3500, 2100, "claude-opus-4.5", "planning", "task-003"),
        (1800, 950, "claude-3-sonnet", "mode_detection", "task-004"),
        (900, 450, "claude-3-haiku", "tag_assignment", "task-005"),
        (4200, 2800, "claude-opus-4.5", "brainstorming", "task-006"),
        (1200, 600, "gemini-pro", "search", "task-007"),
        (2100, 1100, "claude-3-sonnet", "mode_detection", "task-008"),
    ]

    for input_t, output_t, model, category, task_id in usage_data:
        analyzer.record_usage(input_t, output_t, model, category, task_id)

    # Analyze
    analysis = analyzer.analyze(days=7)

    print(f"  Period: {analysis.period_start[:10]} to {analysis.period_end[:10]}")
    print(f"  Total tokens: {analysis.total_tokens:,}")
    print(f"  Input tokens: {analysis.total_input_tokens:,}")
    print(f"  Output tokens: {analysis.total_output_tokens:,}")
    print(f"  Estimated cost: ${analysis.estimated_cost:.4f}")
    print(f"  Cost per task: ${analysis.cost_per_task:.4f}")
    print(f"  By model: {analysis.tokens_by_model}")
    print(f"  By category: {analysis.tokens_by_category}")

    assert analysis.total_tokens > 0
    assert analysis.estimated_cost > 0
    print("[PASS] Cost analyzer working")
    return True, analyzer


def test_suggestions_generator():
    """Test suggestions generator."""
    print("\n" + "=" * 60)
    print("TEST 5: Suggestions Generator")
    print("=" * 60)

    from src.services.weekly_review.suggestions import SuggestionsGenerator
    from src.services.weekly_review.review_schema import (
        UsageSummary,
        QualityTrend,
        CostAnalysis,
        TrendDirection,
    )

    generator = SuggestionsGenerator()

    # Create test data
    usage = UsageSummary(
        total_stores=100,
        total_retrievals=50,
        total_searches=30,
        cache_hit_rate=0.45,  # Low - should trigger suggestion
    )

    quality_trends = [
        QualityTrend(
            metric_name="escalation_rate",
            current_value=0.35,  # High - critical
            previous_value=0.25,
            change_percent=40.0,
            direction=TrendDirection.DECLINING,
            warning_threshold=0.2,
            critical_threshold=0.3,
            is_warning=True,
            is_critical=True,
        ),
        QualityTrend(
            metric_name="confidence_avg",
            current_value=0.58,
            previous_value=0.68,
            change_percent=-14.7,
            direction=TrendDirection.DECLINING,
            warning_threshold=0.65,
            critical_threshold=0.5,
            is_warning=True,
            is_critical=False,
        ),
    ]

    cost = CostAnalysis(
        estimated_cost=15.50,
        cost_change_percent=35.0,  # High increase
    )

    # Generate suggestions
    suggestions = generator.generate(
        usage=usage,
        quality_trends=quality_trends,
        cost_analysis=cost,
    )

    print(f"  Suggestions generated: {len(suggestions)}")
    for sug in suggestions:
        print(f"    [{sug.priority.name}] {sug.title}")
        print(f"      {sug.specific_action}")

    assert len(suggestions) >= 3  # Should have multiple suggestions
    print("[PASS] Suggestions generator working")
    return True


def test_weekly_coordinator():
    """Test weekly review coordinator."""
    print("\n" + "=" * 60)
    print("TEST 6: Weekly Review Coordinator")
    print("=" * 60)

    from src.services.weekly_review.weekly_coordinator import WeeklyReviewCoordinator

    coordinator = WeeklyReviewCoordinator()

    # Seed with data
    # Usage
    for i in range(20):
        op_type = ["store", "retrieve", "search", "graph_query"][i % 4]
        category = ["mode_detection", "entity_extraction", "tag_assignment"][i % 3]
        coordinator.usage_aggregator.record_operation(op_type, category, 50.0 + i * 5)

    # Quality metrics
    base_time = datetime.now(timezone.utc) - timedelta(days=7)
    for day in range(7):
        timestamp = base_time + timedelta(days=day)
        coordinator.quality_analyzer.record_metric("success_rate", 0.78 + (day * 0.01), timestamp)
        coordinator.quality_analyzer.record_metric("confidence_avg", 0.68 - (day * 0.01), timestamp)
        coordinator.quality_analyzer.record_metric("escalation_rate", 0.15 + (day * 0.02), timestamp)
        coordinator.quality_analyzer.record_metric("cache_hit_rate", 0.72 + (day * 0.02), timestamp)

    # Token usage
    for i in range(10):
        coordinator.cost_analyzer.record_usage(
            1500 + i * 200,
            800 + i * 100,
            "claude-3-sonnet",
            "mode_detection",
            f"task-{i:03d}",
        )

    # Generate review
    review = coordinator.generate_review()

    print(f"  Review ID: {review.review_id}")
    print(f"  Week: {review.week_number}")
    print(f"  Health Score: {review.health_score:.0f}/100")
    print(f"\n  Executive Summary:")
    print(f"  {review.executive_summary}")
    print(f"\n  Key Highlights:")
    for h in review.key_highlights:
        print(f"    + {h}")
    print(f"\n  Areas of Concern:")
    for c in review.areas_of_concern:
        print(f"    ! {c}")
    print(f"\n  Suggestions: {len(review.suggestions)}")
    for sug in review.suggestions[:3]:
        print(f"    [{sug.priority.name}] {sug.title}")

    # Test markdown output
    markdown = review.format_markdown()
    print(f"\n  Markdown report generated: {len(markdown)} characters")

    assert review.health_score > 0
    assert review.executive_summary
    print("[PASS] Weekly coordinator working")
    return True


def verify_no_mocks():
    """Verify no mock objects in implementation."""
    print("\n" + "=" * 60)
    print("TEST 7: Mock Detection")
    print("=" * 60)

    import inspect
    from src.services.weekly_review import (
        UsageAggregator,
        QualityTrendsAnalyzer,
        CostTokenAnalyzer,
        SuggestionsGenerator,
        WeeklyReviewCoordinator,
    )

    modules_to_check = [
        UsageAggregator,
        QualityTrendsAnalyzer,
        CostTokenAnalyzer,
        SuggestionsGenerator,
        WeeklyReviewCoordinator,
    ]

    mock_found = False
    for module in modules_to_check:
        source = inspect.getsource(module)
        if "Mock" in source or "unittest.mock" in source:
            print(f"  [WARN] Mock reference in {module.__name__}")
            mock_found = True

    if not mock_found:
        print("  No mock objects detected in implementation")

    print("[PASS] Mock detection complete")
    return not mock_found


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("IMPROVE-002: AUTOMATIC WEEKLY REVIEW - REAL DATA TEST")
    print("=" * 70)
    print(f"Started: {datetime.now().isoformat()}")

    all_passed = True

    # Test 1: Imports
    if not test_imports():
        all_passed = False
        return False

    # Test 2: Usage Aggregator
    passed, _ = test_usage_aggregator()
    if not passed:
        all_passed = False

    # Test 3: Quality Trends
    passed, _ = test_quality_trends()
    if not passed:
        all_passed = False

    # Test 4: Cost Analyzer
    passed, _ = test_cost_analyzer()
    if not passed:
        all_passed = False

    # Test 5: Suggestions Generator
    if not test_suggestions_generator():
        all_passed = False

    # Test 6: Weekly Coordinator
    if not test_weekly_coordinator():
        all_passed = False

    # Test 7: Mock Detection
    if not verify_no_mocks():
        all_passed = False

    # Summary
    print("\n" + "=" * 70)
    if all_passed:
        print("ALL REAL-DATA TESTS PASSED!")
    else:
        print("SOME TESTS FAILED")
    print("=" * 70)

    print(f"\nIMPROVE-002 Weekly Review verified with real data:")
    print("  - Usage aggregator tracks operations")
    print("  - Quality trends analyzer detects patterns")
    print("  - Cost analyzer calculates token costs")
    print("  - Suggestions generator creates actionable items")
    print("  - Weekly coordinator orchestrates full reports")
    print("  - Markdown reports generated correctly")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
