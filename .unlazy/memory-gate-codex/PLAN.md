# Codex memory gate compatibility plan

Scope: reuse the verified Claude memory-gate handlers from memory-mcp for Codex
without duplicating state machines or weakening Claude behavior.

## Contract

1. Codex `apply_patch` is treated as an edit by both PreToolUse and PostToolUse.
   Codex-normalized `mcp__memory_mcp__*` names are accepted alongside Claude's
   `mcp__memory-mcp__*` names.
2. A successful Codex Stop hook always emits valid JSON; a blocked Stop still
   exits 2 with the existing memory remedy. SessionStart wraps its context in
   Codex's structured JSON output while Claude retains plain-text context.
3. User-level `C:/Users/17175/.codex/hooks.json` uses the repository venv and
   registers the shared
   SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, and Stop handlers
   exactly once. The PreToolUse matcher covers Codex `apply_patch` only.
4. The exact installed hook definitions are reviewed and trusted for future
   Codex sessions. Validation may use `--dangerously-bypass-hook-trust`, but that
   flag is not an acceptable substitute for persisted trust.
5. The loaded effective hook set is queried through `hooks/list`; its current
   hashes are recorded in Codex's existing `[hooks.state]` format and then
   re-queried as trusted. Two real Codex sessions without the trust-bypass flag,
   with the dirty session resumed for deterministic waiver recovery,
   proves prompt marker, an observed first-denial, retrieval receipt, edit
   timestamp, Stop waiver consumption, and no one-shot bypass on the credited
   edit.
6. Existing Claude hook tests and the full repository suite remain green.

## Delivery

1. Add fail-first tests using the captured Codex payload shapes.
2. Make the minimal shared compatibility changes: edit aliases, normalized MCP
   names, platform-correct remedy text, and valid Codex Stop success output.
3. Obtain a read-only Claude Opus review and rerun focused checks.
4. Commit and fast-forward the verified branch to main before installing the
   global Codex hook file, because its commands target the live checkout.
5. Back up `hooks.json` and `config.toml`, install the exact hook groups, query
   their effective keys and current hashes, record trust, and run a real Codex
   smoke. Roll back by restoring those two backup files if any live gate fails.
6. Run final focused/full checks, independent audit, and fresh acceptance gates;
   then push main.

## Boundaries

- Do not create a second Codex-specific memory implementation or plugin.
- Do not add SessionEnd; per-turn Stop is the contract and SessionEnd is
  advisory.
- Do not change the existing memory database or Claude hook configuration.
- Hooks remain a guardrail: hosted tools and specialized tool paths can bypass
  local tool hooks, as documented by OpenAI.
- The live verifier uses Codex's approval reviewer for its isolated temporary
  workspaces, but never bypasses persisted hook trust.

## Runtime probe

- Codex CLI 0.149.1 reported `apply_patch` in both PreToolUse and PostToolUse.
- The configured server `memory-mcp` was normalized to
  `mcp__memory_mcp__unified_search`, not Claude's hyphenated spelling.
- Successful retrieval PostToolUse used a dictionary response containing
  `content` and `isError: false`.
- Stop included `session_id`, `turn_id`, `stop_hook_active: false`, and
  `last_assistant_message`.
- The original user hook file was restored to its exact SHA-256 after probing.
