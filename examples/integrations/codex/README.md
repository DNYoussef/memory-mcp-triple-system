# Codex Integration Example

This directory contains a sanitized reference for connecting Codex to the
Memory MCP stdio server.

Copy or adapt these files into your Codex configuration location:

- `memory_mcp_wrapper.py` - stdio wrapper that supports both line-delimited JSON
  and `Content-Length` framed MCP messages.
- `config.memory-mcp.toml` - example Codex MCP server stanza.

Codex lifecycle hooks can reuse the handlers in `src/hooks`. Register
SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, and Stop in
`~/.codex/hooks.json`, using the repository virtual environment to run them.
The shared handlers accept Codex's `apply_patch` edit name and normalized
`mcp__memory_mcp__*` tool names while retaining Claude compatibility. Review and
trust the resulting hook hashes with `/hooks` before relying on the gate. The
edit gate covers Codex's native `apply_patch` event; writes hidden inside shell
commands do not produce that event and are outside this hook's scope.

Set `MEMORY_MCP_ROOT` to the absolute path of your local
`memory-mcp-triple-system` checkout. The hooks default to
`~/.claude/memory-mcp-data/agent_kv.db`, so point `MEMORY_MCP_DATA_DIR` at
`~/.claude/memory-mcp-data` as shown. A custom hook environment must set
`MEMORY_MCP_DB` to the full path of the same `agent_kv.db`. Do not commit
machine-local paths or credentials.
