"""F4: stdout/stderr must be forced to UTF-8 so a cp1252 pipe does not crash
the process when a library prints a non-cp1252 glyph at import time."""
import sys

from src.mcp import _utf8_io


class _FakeStream:
    def __init__(self, encoding):
        self.encoding = encoding
        self.reconfigured = None

    def reconfigure(self, encoding, errors):
        self.encoding = encoding
        self.reconfigured = (encoding, errors)


def _run_with(stdout, stderr):
    o, e = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = stdout, stderr
    try:
        _utf8_io.ensure_utf8_io()
    finally:
        sys.stdout, sys.stderr = o, e


def test_cp1252_stream_is_reconfigured_to_utf8():
    out, err = _FakeStream("cp1252"), _FakeStream("cp1252")
    _run_with(out, err)
    assert out.reconfigured == ("utf-8", "replace")
    assert err.reconfigured == ("utf-8", "replace")


def test_utf8_stream_is_left_alone():
    out, err = _FakeStream("utf-8"), _FakeStream("UTF-8")
    _run_with(out, err)
    assert out.reconfigured is None
    assert err.reconfigured is None


def test_non_reconfigurable_stream_does_not_raise():
    class NoReconfigure:
        encoding = "cp1252"
    # object without reconfigure() must be swallowed, not raised
    _run_with(NoReconfigure(), NoReconfigure())


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
