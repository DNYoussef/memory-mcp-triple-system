"""Services for memory system components."""


def __getattr__(name):
    """Lazy import to avoid spacy cascade import issues."""
    if name == "EntityConsolidator":
        from .entity_service import EntityConsolidator
        return EntityConsolidator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["EntityConsolidator"]
