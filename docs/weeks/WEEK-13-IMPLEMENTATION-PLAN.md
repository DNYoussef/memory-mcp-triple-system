# Week 13 Implementation Plan: Mode-Aware Context

**Version**: 1.0
**Date**: 2025-10-18
**Status**: Ready to Implement
**Methodology**: Loop 2 (Queen implements directly)

---

## Overview

Week 13 implements **mode-aware context** by formalizing the mode configuration system. This builds on Week 11's curated core pattern (execution: 5+0, planning: 5+15, brainstorming: 5+25) by creating dedicated `ModeProfile` and `ModeDetector` classes.

**Source**: PLAN v7.0 FINAL lines 771-783, SPEC v7.0 EXECUTIVE SUMMARY

---

## Deliverables

### Production Code (240 LOC)

**src/modes/__init__.py** (12 LOC):
- Module initialization
- Export ModeProfile, ModeDetector

**src/modes/mode_profile.py** (120 LOC):
- `ModeProfile` dataclass defining mode configuration
- 3 predefined profiles: execution, planning, brainstorming
- Configuration includes:
  - `core_size` - Number of core results
  - `extended_size` - Number of extended results
  - `verification_enabled` - Enable ground truth verification
  - `constraints_enabled` - Enable error constraints
  - `latency_budget_ms` - Maximum latency
  - `token_budget` - Maximum tokens
  - `randomness` - Random injection rate (0-1)

**src/modes/mode_detector.py** (108 LOC):
- `ModeDetector` class for pattern-based mode detection
- Detection patterns:
  - Execution: "What is X?", "How do I X?", imperative queries
  - Planning: "What should I X?", "How can I X?", conditional queries
  - Brainstorming: "What if X?", "Could we X?", creative queries
- Confidence scoring (0-1)
- Fallback to default mode if confidence <0.7

### Test Code (200 LOC)

**tests/unit/test_mode_profile.py** (100 LOC, 5 tests):
1. `test_mode_profile_creation` - Verify profile attributes
2. `test_execution_mode_profile` - Execution configuration
3. `test_planning_mode_profile` - Planning configuration
4. `test_brainstorming_mode_profile` - Brainstorming configuration
5. `test_mode_profile_validation` - Invalid configurations

**tests/unit/test_mode_detector.py** (100 LOC, 5 tests):
1. `test_detect_execution_mode` - Execution patterns
2. `test_detect_planning_mode` - Planning patterns
3. `test_detect_brainstorming_mode` - Brainstorming patterns
4. `test_mode_detection_confidence` - Confidence scoring
5. `test_mode_detection_fallback` - Low confidence fallback

---

## Architecture

### Mode Profile Structure

```python
@dataclass
class ModeProfile:
    """
    Mode-specific configuration profile.

    Insight #5: Mode awareness > prompt cleverness.
    Different modes need different retrieval strategies.
    """
    name: str                    # execution/planning/brainstorming
    core_size: int               # Curated core (precision)
    extended_size: int           # Extended results (recall)
    verification_enabled: bool   # Ground truth verification
    constraints_enabled: bool    # Error constraints
    latency_budget_ms: int       # Maximum latency
    token_budget: int            # Maximum tokens
    randomness: float            # Random injection (0-1)
```

### Predefined Profiles

**Execution Mode** (precision-optimized):
```python
EXECUTION = ModeProfile(
    name="execution",
    core_size=5,
    extended_size=0,          # No extended (precision only)
    verification_enabled=True, # Verify against ground truth
    constraints_enabled=True,  # Strict error handling
    latency_budget_ms=500,    # Fast response
    token_budget=5000,        # Minimal context
    randomness=0.0            # No randomness
)
```

**Planning Mode** (balanced):
```python
PLANNING = ModeProfile(
    name="planning",
    core_size=5,
    extended_size=15,         # 5 + 15 = 20 total
    verification_enabled=True,
    constraints_enabled=True,
    latency_budget_ms=1000,   # Medium response
    token_budget=10000,       # Balanced context
    randomness=0.05           # 5% random injection
)
```

**Brainstorming Mode** (recall-optimized):
```python
BRAINSTORMING = ModeProfile(
    name="brainstorming",
    core_size=5,
    extended_size=25,         # 5 + 25 = 30 total
    verification_enabled=False, # No verification (allow creative errors)
    constraints_enabled=False,  # No constraints
    latency_budget_ms=2000,    # Slower response OK
    token_budget=20000,        # Large context
    randomness=0.10            # 10% random injection
)
```

### Mode Detection Patterns

**Execution Patterns** (high precision):
- "What is X?"
- "How do I X?"
- "Show me X"
- "Get X"
- "Find X"
- Imperative verbs (get, show, find, fetch)

**Planning Patterns** (balanced):
- "What should I X?"
- "How can I X?"
- "What are the options for X?"
- "Compare X and Y"
- Conditional/comparative queries

**Brainstorming Patterns** (high recall):
- "What if X?"
- "Could we X?"
- "Imagine X"
- "Explore X"
- "What are all possible X?"
- Creative/exploratory verbs

### Detection Algorithm

```python
def detect(query: str) -> Tuple[ModeProfile, float]:
    """
    Detect mode from query using pattern matching.

    Returns:
        (profile, confidence)

    Confidence threshold: 0.7
    If confidence < 0.7, use default (execution)
    """
    scores = {
        'execution': _score_execution_patterns(query),
        'planning': _score_planning_patterns(query),
        'brainstorming': _score_brainstorming_patterns(query)
    }

    mode = max(scores, key=scores.get)
    confidence = scores[mode]

    if confidence < 0.7:
        return EXECUTION, 0.5  # Fallback to execution

    return PROFILES[mode], confidence
```

---

## Implementation Phases

### Phase 1: Mode Profile (6 hours)

**Files**:
- `src/modes/__init__.py` (12 LOC)
- `src/modes/mode_profile.py` (120 LOC)

**Classes**:
1. `ModeProfile` dataclass
2. Predefined profiles: `EXECUTION`, `PLANNING`, `BRAINSTORMING`
3. Helper: `get_profile(name: str) -> ModeProfile`

**Success Criteria**:
- All profiles have required attributes
- Validation prevents invalid configs
- Type hints 100%

### Phase 2: Mode Detector (6 hours)

**Files**:
- `src/modes/mode_detector.py` (108 LOC)

**Methods**:
1. `detect(query: str) -> Tuple[ModeProfile, float]`
2. `_score_execution_patterns(query: str) -> float`
3. `_score_planning_patterns(query: str) -> float`
4. `_score_brainstorming_patterns(query: str) -> float`
5. `_extract_patterns(query: str) -> List[str]`

**Success Criteria**:
- Pattern matching works for all 3 modes
- Confidence scoring (0-1)
- Fallback to execution if confidence <0.7
- All methods ≤60 LOC

### Phase 3: Testing (6 hours)

**Files**:
- `tests/unit/test_mode_profile.py` (100 LOC, 5 tests)
- `tests/unit/test_mode_detector.py` (100 LOC, 5 tests)

**Test Coverage**:
- Profile creation and validation
- Detection accuracy (≥85% target)
- Confidence scoring
- Edge cases (empty queries, ambiguous patterns)

**Success Criteria**:
- 10/10 tests passing
- ≥80% code coverage
- Detection accuracy ≥85%

### Phase 4: Audits (2 hours)

**3-Part Audit**:
1. Theater Detection (0 violations expected)
2. Functionality (10/10 tests passing)
3. Style/NASA (100% compliance)

---

## Integration Points

### Nexus Processor (Week 11)

**Current State**:
```python
# src/nexus/processor.py - compress() method
def compress(self, ranked_results, mode: str, token_budget):
    # Hardcoded mode configuration
    if mode == 'execution':
        core_size = 5
        extended_size = 0
    elif mode == 'planning':
        core_size = 5
        extended_size = 15
    elif mode == 'brainstorming':
        core_size = 5
        extended_size = 25
```

**Week 13 Enhancement** (Future Integration):
```python
from src.modes import ModeProfile, ModeDetector

class NexusProcessor:
    def __init__(self, ...):
        self.mode_detector = ModeDetector()

    def process(self, query: str, mode: Optional[str] = None):
        # Auto-detect mode if not specified
        if mode is None:
            profile, confidence = self.mode_detector.detect(query)
            logger.info(f"Detected mode: {profile.name} (confidence: {confidence:.2f})")
        else:
            profile = get_profile(mode)

        # Use profile configuration
        results = self.compress(
            ranked_results,
            core_size=profile.core_size,
            extended_size=profile.extended_size,
            token_budget=profile.token_budget
        )
```

**Note**: Nexus Processor integration is OPTIONAL for Week 13. Week 13 focuses on creating the mode system. Integration can be done in Week 14 or later.

### Query Trace (Week 7-8)

**Enhancement** (Future Integration):
```python
# src/debug/query_trace.py
class QueryTrace:
    mode_detected: str          # NEW: detected mode
    mode_confidence: float      # NEW: detection confidence
    mode_override: Optional[str] # NEW: manual override
```

**Note**: Query trace integration is for Week 14 (error attribution dashboard).

---

## Performance Targets

| Operation | Target | Rationale |
|-----------|--------|-----------|
| Mode detection | <10ms | Pattern matching only |
| Profile lookup | <1ms | Dictionary access |
| Pattern scoring | <5ms | Regex matching |

---

## Quality Assurance

### 3-Part Audit

1. **Theater Detection** (target: 100/100):
   - 0 TODO comments
   - 0 mock data
   - 0 hardcoded patterns (patterns are configuration, not theater)

2. **Functionality** (target: 100/100):
   - 10/10 tests passing
   - Detection accuracy ≥85%
   - All modes correctly configured

3. **Style (NASA Rule 10)** (target: 100/100):
   - All methods ≤60 LOC
   - 100% type hints
   - Full docstrings

### Detection Accuracy Target

**Test Dataset**: 100 queries (provided in tests)
- 33 execution queries
- 33 planning queries
- 34 brainstorming queries

**Target Accuracy**: ≥85% (85/100 correct detections)

**Measurement**:
```python
def test_detection_accuracy():
    detector = ModeDetector()
    correct = 0

    for query, expected_mode in test_dataset:
        profile, confidence = detector.detect(query)
        if profile.name == expected_mode:
            correct += 1

    accuracy = correct / len(test_dataset)
    assert accuracy >= 0.85, f"Accuracy {accuracy:.1%} below 85% target"
```

---

## Risk Mitigation

**Risk**: Pattern-based detection may have low accuracy
- **Mitigation**: 100-query test dataset, tunable confidence threshold
- **Validation**: Accuracy test required (≥85%)

**Risk**: Mode profiles may need adjustment
- **Mitigation**: Profiles are dataclasses (easy to modify)
- **Validation**: Profile validation tests

**Risk**: Ambiguous queries may be misclassified
- **Mitigation**: Confidence threshold (0.7), fallback to execution
- **Validation**: Edge case tests

---

## Timeline

**Total**: 20 hours (2.5 working days)

- **Phase 1** (6 hours): Mode Profile class + predefined profiles
- **Phase 2** (6 hours): Mode Detector + pattern matching
- **Phase 3** (6 hours): Testing (10 tests)
- **Phase 4** (2 hours): 3-part audit + documentation

**Checkpoint**: After Phase 1, verify:
- ✅ 3 mode profiles defined
- ✅ All attributes validated
- ✅ Type hints complete

**Checkpoint**: After Phase 2, verify:
- ✅ Detection works for all 3 modes
- ✅ Confidence scoring functional
- ✅ All methods ≤60 LOC

---

## Success Criteria

**Production Code**:
- ✅ 240 LOC implemented (mode_profile.py + mode_detector.py)
- ✅ All methods ≤60 LOC (NASA Rule 10)
- ✅ 100% type hints
- ✅ Full docstrings

**Test Code**:
- ✅ 200 LOC tests
- ✅ 10 tests passing (100%)
- ✅ ≥80% code coverage
- ✅ Detection accuracy ≥85%

**Quality**:
- ✅ Theater: 100/100 (0 violations)
- ✅ Functionality: 100/100 (10/10 tests)
- ✅ Style: 100/100 (≥95% NASA compliance)

**Integration**:
- ✅ Mode system ready for Nexus Processor integration
- ✅ Mode profiles ready for Query Trace integration
- ✅ Detection ready for Week 14 dashboard

---

**Plan Created**: 2025-10-18
**Agent**: Claude Code (Queen)
**Loop**: Loop 2 (Direct Implementation)
**Status**: Ready to Execute
