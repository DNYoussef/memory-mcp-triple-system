"""
Unit tests for Mode Detector.

Tests pattern-based mode detection and confidence scoring.
"""

import pytest
from src.modes.mode_detector import ModeDetector
from src.modes.mode_profile import EXECUTION, PLANNING, BRAINSTORMING


class TestModeDetection:
    """Test suite for mode detection."""

    @pytest.fixture
    def detector(self):
        """Create mode detector instance."""
        return ModeDetector()

    def test_detect_execution_mode_what_is(self, detector):
        """Test execution mode detection for 'What is X?' pattern."""
        profile, confidence = detector.detect("What is NASA Rule 10?")

        assert profile == EXECUTION
        assert confidence >= 0.7

    def test_detect_execution_mode_how_do_i(self, detector):
        """Test execution mode detection for 'How do I X?' pattern."""
        profile, confidence = detector.detect("How do I configure pytest?")

        assert profile == EXECUTION
        assert confidence >= 0.7

    def test_detect_execution_mode_show_me(self, detector):
        """Test execution mode detection for 'Show me X' pattern."""
        profile, confidence = detector.detect("Show me the test results")

        assert profile == EXECUTION
        assert confidence >= 0.7

    def test_detect_planning_mode_what_should(self, detector):
        """Test planning mode detection for 'What should I X?' pattern."""
        profile, confidence = detector.detect("What should I implement first?")

        assert profile == PLANNING
        assert confidence >= 0.7

    def test_detect_planning_mode_how_can(self, detector):
        """Test planning mode detection for 'How can I X?' pattern."""
        profile, confidence = detector.detect("How can I improve performance?")

        assert profile == PLANNING
        assert confidence >= 0.7

    def test_detect_planning_mode_compare(self, detector):
        """Test planning mode detection for 'Compare X' pattern."""
        profile, confidence = detector.detect("Compare TypeScript and Python for this task")

        assert profile == PLANNING
        assert confidence >= 0.7

    def test_detect_brainstorming_mode_what_if(self, detector):
        """Test brainstorming mode detection for 'What if X?' pattern."""
        profile, confidence = detector.detect("What if we used a different approach?")

        assert profile == BRAINSTORMING
        assert confidence >= 0.7

    def test_detect_brainstorming_mode_could_we(self, detector):
        """Test brainstorming mode detection for 'Could we X?' pattern."""
        profile, confidence = detector.detect("Could we explore alternative designs?")

        assert profile == BRAINSTORMING
        assert confidence >= 0.7

    def test_detect_brainstorming_mode_imagine(self, detector):
        """Test brainstorming mode detection for 'Imagine X' pattern."""
        profile, confidence = detector.detect("Imagine we had unlimited resources")

        assert profile == BRAINSTORMING
        assert confidence >= 0.7


class TestDetectionConfidence:
    """Test suite for confidence scoring."""

    @pytest.fixture
    def detector(self):
        """Create mode detector instance."""
        return ModeDetector()

    def test_high_confidence_multiple_patterns(self, detector):
        """Test high confidence when multiple patterns match."""
        # Query with multiple execution patterns
        profile, confidence = detector.detect(
            "What is the syntax? How do I use it? Show me an example."
        )

        assert profile == EXECUTION
        assert confidence >= 0.9  # High confidence (3+ patterns)

    def test_medium_confidence_single_pattern(self, detector):
        """Test medium confidence when single pattern matches."""
        profile, confidence = detector.detect("What is this?")

        assert profile == EXECUTION
        assert 0.3 <= confidence < 0.9  # Medium confidence (1 pattern)

    def test_low_confidence_fallback(self, detector):
        """Test fallback to execution for low confidence."""
        # Ambiguous query with no clear patterns
        profile, confidence = detector.detect("The quick brown fox")

        assert profile == EXECUTION  # Fallback
        assert confidence == 0.5  # Fallback confidence

    def test_empty_query_fallback(self, detector):
        """Test fallback for empty query."""
        profile, confidence = detector.detect("")

        assert profile == EXECUTION
        assert confidence == 0.5


class TestDetectionAccuracy:
    """Test suite for overall detection accuracy."""

    @pytest.fixture
    def detector(self):
        """Create mode detector instance."""
        return ModeDetector()

    def test_detection_accuracy(self, detector):
        """Test detection accuracy on 100-query dataset."""
        # Test dataset: (query, expected_mode)
        test_dataset = [
            # Execution queries (33)
            ("What is X?", "execution"),
            ("What are the steps?", "execution"),
            ("How do I configure this?", "execution"),
            ("How to install dependencies?", "execution"),
            ("Show me the code", "execution"),
            ("Get the latest version", "execution"),
            ("Find all occurrences", "execution"),
            ("Fetch user data", "execution"),
            ("Tell me about NASA Rule 10", "execution"),
            ("Explain the concept", "execution"),
            ("Describe the architecture", "execution"),
            ("What is the difference?", "execution"),
            ("How do I debug this?", "execution"),
            ("Show me examples", "execution"),
            ("Get test results", "execution"),
            ("Find the bug", "execution"),
            ("Tell me the status", "execution"),
            ("Explain how it works", "execution"),
            ("What are the requirements?", "execution"),
            ("How do I run tests?", "execution"),
            ("Show me the logs", "execution"),
            ("Get performance metrics", "execution"),
            ("Find memory leaks", "execution"),
            ("What is the error?", "execution"),
            ("Describe the problem", "execution"),
            ("Tell me what failed", "execution"),
            ("How to fix this?", "execution"),
            ("What are the symptoms?", "execution"),
            ("Show me stack trace", "execution"),
            ("Get error details", "execution"),
            ("Find root cause", "execution"),
            ("What is causing slowness?", "execution"),
            ("Explain the failure", "execution"),

            # Planning queries (33)
            ("What should I do first?", "planning"),
            ("How can I improve this?", "planning"),
            ("How should I proceed?", "planning"),
            ("What are the options for deployment?", "planning"),
            ("Compare React and Vue", "planning"),
            ("Which is better: REST or GraphQL?", "planning"),
            ("Should I use TypeScript?", "planning"),
            ("When should I refactor?", "planning"),
            ("What if I chose a different approach?", "planning"),
            ("What should I prioritize?", "planning"),
            ("How can I optimize performance?", "planning"),
            ("What are the trade-offs?", "planning"),
            ("Should I migrate now?", "planning"),
            ("What should I test first?", "planning"),
            ("How can I reduce complexity?", "planning"),
            ("Which database should I use?", "planning"),
            ("What should I focus on?", "planning"),
            ("How can I scale this?", "planning"),
            ("What are the risks?", "planning"),
            ("Should I add caching?", "planning"),
            ("What if I need more features?", "planning"),
            ("How should I structure this?", "planning"),
            ("What are the best practices?", "planning"),
            ("Should I split this module?", "planning"),
            ("How can I make this testable?", "planning"),
            ("What should I document?", "planning"),
            ("Which pattern should I use?", "planning"),
            ("How can I improve maintainability?", "planning"),
            ("What are the alternatives?", "planning"),
            ("Should I use a framework?", "planning"),
            ("How should I handle errors?", "planning"),
            ("What are the pros and cons?", "planning"),
            ("Which approach is more scalable?", "planning"),

            # Brainstorming queries (34)
            ("What if we used microservices?", "brainstorming"),
            ("Could we explore event sourcing?", "brainstorming"),
            ("Imagine unlimited compute resources", "brainstorming"),
            ("Explore all possible architectures", "brainstorming"),
            ("What are all the ways to solve this?", "brainstorming"),
            ("What other technologies could we use?", "brainstorming"),
            ("List all possible optimizations", "brainstorming"),
            ("Brainstorm deployment strategies", "brainstorming"),
            ("Ideas for improving user experience", "brainstorming"),
            ("What if we rewrote everything?", "brainstorming"),
            ("Could we use machine learning?", "brainstorming"),
            ("Imagine we had no constraints", "brainstorming"),
            ("Explore creative solutions", "brainstorming"),
            ("What are all possible features?", "brainstorming"),
            ("What other approaches exist?", "brainstorming"),
            ("List all potential issues", "brainstorming"),
            ("Brainstorm test scenarios", "brainstorming"),
            ("What if we started over?", "brainstorming"),
            ("Could we automate everything?", "brainstorming"),
            ("What are all the edge cases?", "brainstorming"),
            ("Explore unconventional ideas", "brainstorming"),
            ("What if performance wasn't a concern?", "brainstorming"),
            ("Could we build this differently?", "brainstorming"),
            ("Imagine perfect conditions", "brainstorming"),
            ("What are all the risks?", "brainstorming"),
            ("List all potential benefits", "brainstorming"),
            ("Brainstorm integration points", "brainstorming"),
            ("What other use cases exist?", "brainstorming"),
            ("Could we extend this further?", "brainstorming"),
            ("What if we had more time?", "brainstorming"),
            ("Explore all variations", "brainstorming"),
            ("What are all the dependencies?", "brainstorming"),
            ("List all possible improvements", "brainstorming"),
            ("Brainstorm monitoring strategies", "brainstorming")
        ]

        correct = 0
        for query, expected_mode in test_dataset:
            profile, confidence = detector.detect(query)
            if profile.name == expected_mode:
                correct += 1

        accuracy = correct / len(test_dataset)

        # Target: ≥85% accuracy
        assert accuracy >= 0.85, (
            f"Detection accuracy {accuracy:.1%} below 85% target "
            f"({correct}/{len(test_dataset)} correct)"
        )
