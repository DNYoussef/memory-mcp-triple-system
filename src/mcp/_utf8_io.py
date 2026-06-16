"""Force UTF-8 on stdout/stderr (F4).

On Windows a non-tty stdout defaults to cp1252. Some libraries (e.g.
transformers) print a non-cp1252 glyph at import time, which raises
UnicodeEncodeError and crashes the process - and the MCP stdio transport always
runs with stdout as a pipe. Importing this module first reconfigures both
streams to UTF-8 (errors="replace") before those imports run.

Idempotent and safe: the JSON-RPC framing writes to sys.stdout.buffer (binary),
which reconfigure does not affect.
"""
import sys


def ensure_utf8_io() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            enc = (getattr(stream, "encoding", "") or "").lower()
            if stream is not None and enc not in ("utf-8", "utf8"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            # Old Python without reconfigure, or a non-reconfigurable stream.
            pass


ensure_utf8_io()
