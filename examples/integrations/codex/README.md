# Codex Integration Example

This directory contains a sanitized reference for connecting Codex to the
Memory MCP stdio server.

Copy or adapt these files into your Codex configuration location:

- `memory_mcp_wrapper.py` - stdio wrapper that supports both line-delimited JSON
  and `Content-Length` framed MCP messages.
- `config.memory-mcp.toml` - example Codex MCP server stanza.

Set `MEMORY_MCP_ROOT` to the absolute path of your local
`memory-mcp-triple-system` checkout. Do not commit machine-local paths or
credentials.
