"""Regression tests for the SessionStart hook (MECE G8).

The hook prints memory-derived context to stdout; on Windows stdout defaults to
cp1252, so non-ASCII memory content used to crash the hook (UnicodeEncodeError
escaping main(), no context injected). _emit_context must write UTF-8 and never
raise.

Non-ASCII test content uses unicode escapes so this source file stays pure ASCII
(project rule) while the runtime strings under test are non-ASCII.
"""

import io
import sys


from src.hooks.session_start_handler import _emit_context

EM_DASH = chr(0x2014)  # em dash
ACCENTED = "caf" + chr(0xE9) + " r" + chr(0xE9) + "sum" + chr(0xE9)  # cafe resume
ROCKET = chr(0x1F680)  # rocket emoji
NON_ASCII = "Memory: " + ACCENTED + " " + EM_DASH + " rocket " + ROCKET


def test_emit_context_writes_utf8_for_non_ascii(monkeypatch):
    """Non-ASCII content is written as UTF-8 bytes via the binary buffer."""
    buf = io.BytesIO()

    class FakeStdout:
        buffer = buf

        def flush(self):
            pass

    monkeypatch.setattr(sys, "stdout", FakeStdout())

    _emit_context(NON_ASCII)

    out = buf.getvalue().decode("utf-8")
    assert EM_DASH in out  # em dash preserved
    assert ROCKET in out  # emoji preserved
    assert ACCENTED in out  # accented chars preserved
    assert out.endswith("\n")


def test_emit_context_never_raises_on_cp1252_text_stream(monkeypatch):
    """If stdout has no binary buffer and the text write raises (cp1252), the
    hook must still not crash."""

    class Cp1252Stdout:
        # No 'buffer' attribute -> forces the text fallback path.
        def write(self, s):
            s.encode("cp1252")  # raises UnicodeEncodeError on non-ASCII

        def flush(self):
            pass

    monkeypatch.setattr(sys, "stdout", Cp1252Stdout())

    # Must not raise despite the encode failure in the fallback.
    _emit_context("emoji " + ROCKET)


def test_emit_context_plain_ascii_roundtrips(monkeypatch):
    """ASCII content still emits unchanged with a trailing newline."""
    buf = io.BytesIO()

    class FakeStdout:
        buffer = buf

        def flush(self):
            pass

    monkeypatch.setattr(sys, "stdout", FakeStdout())
    _emit_context("plain context")
    assert buf.getvalue() == b"plain context\n"


def test_main_does_not_crash_when_kvstore_fails(monkeypatch):
    """main() must degrade gracefully (not raise) if opening the DB fails -
    KVStore() is inside the guard and close() is suppressed."""
    import src.hooks.session_start_handler as handler

    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    monkeypatch.setattr(handler.os.path, "exists", lambda _p: True)

    def boom(*_a, **_k):
        raise RuntimeError("db locked")

    monkeypatch.setattr(handler, "KVStore", boom)

    # Must return without raising (store stays None -> close() is skipped).
    handler.main()
