"""Token calculator for context injection budget enforcement.

Estimates token count, tracks cumulative usage across injection sections,
and enforces mode-based budgets with graceful truncation.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

from typing import Dict, List, Optional, Tuple


# Mode-based token budgets
MODE_BUDGETS: Dict[str, int] = {
    "execution": 5_000,
    "planning": 10_000,
    "brainstorming": 20_000,
}

# Safety margin: reserve 10% of budget for framing/headers
SAFETY_MARGIN = 0.10


def estimate_tokens(text: str) -> int:
    """Estimate token count for text.

    Uses chars/4 approximation -- accurate to within ~10% for English.
    Good enough. Don't pull in tiktoken for this.

    Args:
        text: Input text

    Returns:
        Estimated token count
    """
    if not text:
        return 0
    return len(text) // 4


def get_budget(mode: str) -> int:
    """Get token budget for a mode, with safety margin applied.

    Args:
        mode: One of execution, planning, brainstorming

    Returns:
        Usable token budget (after safety margin)
    """
    raw = MODE_BUDGETS.get(mode, MODE_BUDGETS["execution"])
    return int(raw * (1.0 - SAFETY_MARGIN))


class TokenTracker:
    """Tracks cumulative token usage across injection sections.

    Usage:
        tracker = TokenTracker(mode="execution")
        ok = tracker.try_add("summary", summary_text)
        ok = tracker.try_add("observations", obs_text)
        remaining = tracker.remaining
    """

    def __init__(self, mode: str = "execution"):
        self.mode = mode
        self.budget = get_budget(mode)
        self.used = 0
        self.sections: Dict[str, int] = {}

    @property
    def remaining(self) -> int:
        """Tokens remaining in budget."""
        return max(0, self.budget - self.used)

    @property
    def is_exhausted(self) -> bool:
        """Whether budget is fully consumed."""
        return self.used >= self.budget

    def try_add(self, section: str, text: str) -> bool:
        """Try to add a section within budget.

        Args:
            section: Section name (for tracking)
            text: Text content to add

        Returns:
            True if full text fits, False if would exceed budget
        """
        tokens = estimate_tokens(text)
        if self.used + tokens > self.budget:
            return False
        self.used += tokens
        self.sections[section] = self.sections.get(section, 0) + tokens
        return True

    def add_truncated(self, section: str, text: str) -> str:
        """Add text, truncating to fit remaining budget.

        Args:
            section: Section name
            text: Text to fit

        Returns:
            Text that fits within remaining budget (may be truncated)
        """
        if not text:
            return ""

        available = self.remaining
        if available <= 0:
            return ""

        tokens = estimate_tokens(text)
        if tokens <= available:
            self.used += tokens
            self.sections[section] = self.sections.get(section, 0) + tokens
            return text

        # Truncate: chars = tokens * 4, trim to available budget
        max_chars = available * 4
        truncated = text[:max_chars]

        # Try to break at last newline or sentence boundary
        last_nl = truncated.rfind("\n")
        if last_nl > max_chars // 2:
            truncated = truncated[:last_nl]

        actual_tokens = estimate_tokens(truncated)
        self.used += actual_tokens
        self.sections[section] = self.sections.get(section, 0) + actual_tokens
        return truncated

    def truncate_list(
        self, section: str, items: List[str]
    ) -> List[str]:
        """Add items from a list until budget exhausted.

        Args:
            section: Section name
            items: List of text items to include

        Returns:
            Items that fit within remaining budget
        """
        result = []
        for item in items:
            tokens = estimate_tokens(item)
            if self.used + tokens > self.budget:
                break
            self.used += tokens
            self.sections[section] = self.sections.get(section, 0) + tokens
            result.append(item)
        return result

    def summary(self) -> Dict[str, int]:
        """Return token usage summary by section."""
        return {
            "mode": self.mode,
            "budget": self.budget,
            "used": self.used,
            "remaining": self.remaining,
            "sections": dict(self.sections),
        }
