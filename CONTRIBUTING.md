# Contributing to Memory MCP Triple System

Thank you for your interest in contributing to the Memory MCP Triple System! This document provides guidelines and best practices for contributing to the project.

## Code of Conduct

Be respectful, collaborative, and constructive in all interactions. We're building this together.

## Getting Started

### Development Setup

1. **Fork the repository** on GitHub

2. **Clone your fork**:
   ```bash
   git clone https://github.com/YOUR_GITHUB_USERNAME/memory-mcp-triple-system.git
   cd memory-mcp-triple-system
   ```

   Note: Replace `YOUR_GITHUB_USERNAME` with your actual GitHub username after forking the repository from https://github.com/DNYoussef/memory-mcp-triple-system

3. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Verify installation**:
   ```bash
   pytest tests/ -v
   flake8 src/ tests/
   mypy src/ --strict
   ```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-number-description
```

Branch naming conventions:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation changes
- `refactor/` - Code refactoring
- `test/` - Test improvements

### 2. Make Your Changes

Follow these principles:

#### NASA Rule 10 Compliance
- **All functions ≤60 lines of code**
- **No recursion** (use iterative alternatives)
- **Fixed loop bounds** (no `while True`)
- **≥2 assertions for critical paths**

Example of a compliant function:
```python
def process_chunks(self, chunks: List[Dict]) -> List[str]:
    """Process chunks and return IDs."""
    assert len(chunks) > 0, "Chunks cannot be empty"
    assert all('text' in c for c in chunks), "All chunks need 'text'"
    
    results = []
    for chunk in chunks:
        # Process chunk (≤60 LOC total)
        results.append(chunk['text'])
    
    return results
```

#### Type Hints
All functions must have type hints:
```python
def search_memories(
    self,
    query: str,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """Search for memories matching query."""
    pass
```

#### Documentation
All public functions need docstrings:
```python
def detect_mode(self, query: str) -> Tuple[ModeProfile, float]:
    """
    Detect query mode using pattern matching.
    
    Args:
        query: User query string
        
    Returns:
        Tuple of (detected mode profile, confidence score)
        
    Example:
        >>> detector = ModeDetector()
        >>> profile, conf = detector.detect("What is X?")
        >>> profile.name
        'execution'
    """
    pass
```

### 3. Write Tests

Every new feature or fix must include tests:

```python
# tests/unit/test_your_feature.py
import pytest
from src.your_module import YourClass

class TestYourFeature:
    @pytest.fixture
    def instance(self):
        return YourClass()
    
    def test_basic_functionality(self, instance):
        """Test basic functionality."""
        result = instance.method()
        assert result is not None
        assert len(result) > 0
    
    def test_edge_case(self, instance):
        """Test edge case handling."""
        with pytest.raises(ValueError):
            instance.method(invalid_input)
```

### 4. Run Quality Checks

Before committing, run all quality checks:

```bash
# Run tests
pytest tests/ -v --cov=src --cov-report=term-missing

# Check code style
flake8 src/ tests/

# Check type safety
mypy src/ --strict

# Check security
bandit -r src/

# Verify NASA compliance (for functions you modified)
python -c "
import ast
with open('src/your_file.py', 'r') as f:
    tree = ast.parse(f.read())
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
        length = node.end_lineno - node.lineno + 1
        if length > 60:
            print(f'{node.name}: {length} LOC (violation)')
"
```

All checks must pass:
- ✅ Tests: 100% passing
- ✅ Coverage: ≥80% (≥90% for new features)
- ✅ Flake8: Zero errors
- ✅ Mypy: Zero errors (strict mode)
- ✅ Bandit: Zero high/medium issues
- ✅ NASA: All functions ≤60 LOC

### 5. Commit Your Changes

Write clear, descriptive commit messages:

```bash
git add .
git commit -m "feat: Add context-aware memory retrieval

- Implement mode detection for query classification
- Add 29 regex patterns (11 execution, 9 planning, 9 brainstorming)
- Achieve 85%+ detection accuracy on benchmark
- Add 14 unit tests with 100% coverage

Closes #42"
```

Commit message format:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `refactor:` - Code refactoring
- `test:` - Test improvements
- `chore:` - Maintenance tasks

### 6. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub with:
- **Clear title** describing the change
- **Description** explaining what/why/how
- **Related issues** (e.g., "Closes #42")
- **Test results** showing all checks passed
- **Screenshots** (if UI changes)

## Pull Request Checklist

Before submitting a PR, verify:

- [ ] All tests pass (`pytest tests/ -v`)
- [ ] Code coverage ≥80% for new code
- [ ] Flake8 passes (`flake8 src/ tests/`)
- [ ] Mypy passes strict mode (`mypy src/ --strict`)
- [ ] Bandit security check passes (`bandit -r src/`)
- [ ] All functions ≤60 LOC (NASA Rule 10)
- [ ] Type hints on all functions
- [ ] Docstrings on all public functions
- [ ] Updated documentation (if needed)
- [ ] Updated README (if needed)
- [ ] Commit messages follow convention

## Testing Guidelines

### Unit Tests
- Test individual functions in isolation
- Use fixtures for setup/teardown
- Test edge cases and error handling
- Aim for 100% coverage

### Integration Tests
- Test multiple components together
- Verify end-to-end workflows
- Use realistic data
- Test common use cases

### Test Organization
```
tests/
├── unit/              # Unit tests
│   ├── test_mode_detector.py
│   ├── test_mode_profile.py
│   └── ...
├── integration/       # Integration tests
│   ├── test_pipeline.py
│   └── ...
└── conftest.py        # Shared fixtures
```

## Documentation Guidelines

### Code Comments
```python
# Explain WHY, not WHAT
# Good:
chunks = filter(lambda c: len(c) > 50, chunks)  # Exclude tiny chunks (<50 chars)

# Bad:
chunks = filter(lambda c: len(c) > 50, chunks)  # Filter chunks by length
```

### Documentation Files
- Update README.md for user-facing changes
- Update relevant docs/ files for architecture changes
- Create new docs/ files for major features

## Performance Guidelines

Target performance metrics:
- Mode detection: <200ms
- Vector search: <150ms
- Chunk ingestion: <50ms per chunk

Profile code if adding expensive operations:
```python
import time

start = time.perf_counter()
result = expensive_operation()
elapsed_ms = (time.perf_counter() - start) * 1000
print(f"Operation took {elapsed_ms:.2f}ms")
```

## Questions or Issues?

- **Bug reports**: Open an issue with reproduction steps at https://github.com/DNYoussef/memory-mcp-triple-system/issues
- **Feature requests**: Open an issue describing the use case at https://github.com/DNYoussef/memory-mcp-triple-system/issues
- **Questions**: Open a discussion at https://github.com/DNYoussef/memory-mcp-triple-system/discussions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to Memory MCP Triple System!
