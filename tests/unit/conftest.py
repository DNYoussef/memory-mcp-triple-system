"""
Test configuration for unit tests.
"""

import sys
import types
import pytest

# Mock spacy before any src imports that transitively depend on it.
# spacy is an optional heavy dependency not installed in CI.
if "spacy" not in sys.modules:
    import importlib.machinery
    _spacy = types.ModuleType("spacy")
    _spacy.load = lambda *a, **kw: None
    _spacy.__path__ = []
    # Provide a real ModuleSpec so importlib.util.find_spec() doesn't crash
    _spacy.__spec__ = importlib.machinery.ModuleSpec("spacy", None)
    sys.modules["spacy"] = _spacy
    _cli = types.ModuleType("spacy.cli")
    _cli.download = lambda *a, **kw: None
    _cli.__spec__ = importlib.machinery.ModuleSpec("spacy.cli", None)
    sys.modules["spacy.cli"] = _cli
    for submod in ("spacy.tokens", "spacy.lang", "spacy.lang.en"):
        m = types.ModuleType(submod)
        m.__spec__ = importlib.machinery.ModuleSpec(submod, None)
        sys.modules[submod] = m
