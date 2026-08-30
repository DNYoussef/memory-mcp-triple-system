# Memory gate v12 implementation plan

Scope: implement the supplied memory-gate specification without changing the
user's live checkout until the isolated branch is verified.

## Delivery phases

1. Establish runtime truth.
   - Capture a real successful memory_store PostToolUse payload.
   - Verify which Claude settings files are actually loaded.
   - Preserve the live checkout byte-for-byte after temporary probing.
2. Reconcile the specification with current code.
   - Trace the three existing hook handlers, KVStore, observation bridge,
     summarizer, settings, and companion integration tests.
   - Obtain a read-only Claude Opus MECE critique.
3. Author acceptance gates and fail-first tests.
   - Cover prompt marker and receipt state, fail-open behavior, dirty/save
     ordering, skip consumption, session-id separation, response-shape handling,
     structured redaction, health output, settings registration, and docs.
   - Prove each decisive probe fails against the unmodified baseline.
4. Implement the smallest complete change in the isolated worktree.
   - Reuse KVStore and existing hook patterns; add no dependency or new store API.
   - Keep hook errors fail-open except for the deliberate PreToolUse deny and
     Stop exit-code-2 decisions.
   - Treat list-shaped retrieval responses as successful because the live
     payload has no reliable business-error bit. Credit list-shaped memory_store
     calls only when the repository's fixed `Stored memory: ` prefix is present.
   - Make the edit denial a one-shot nudge per prompt so an unavailable memory
     server cannot create an unbounded deny loop.
   - Use the script-based UserPromptSubmit injection fallback; the installed
     Claude version silently rejected the proposed mcp_tool hook setting.
5. Verify and install.
   - Run focused tests, integration tests, lint/format checks, and the repository
     test gate appropriate to this change.
   - Merge verified code before changing hook commands that point at the live
     checkout, then move the hook block into loaded user settings and remove the
     old project-local copy so registration is not duplicated.
   - Run live Claude hook smoke probes only after code and settings are installed.
   - Install the hooks in user settings intentionally so they apply to every
     Claude project. Verify from the D-drive repository that the global
     memory-mcp server is available; the edit nudge remains one-shot if it is not.
6. Adversarial audit and delivery.
   - Claude Opus audits the spec, diff, and gates read-only and reruns their
     underlying commands.
   - Codex reruns every approved gate after the final edit.
   - Keep the redaction/capture correction and the memory gate in separate
     logical commits so either behavior can be reverted independently.
   - Report any accepted limitation or blocker explicitly.

## Runtime findings

- The clean live checkout began at b58ba305d3f35630b1172ba0cf68d3fc3047f46b.
- A real successful memory_store PostToolUse payload had tool_response as a raw
  one-element array, with no isError field. The plan's list-shaped branch is
  required.
- The attempted validation-failure call did not execute, so no failure payload
  shape is claimed.
- Claude debug output from a D-drive repository did not load
  C:/Users/17175/.claude/settings.local.json, while a run whose project directory
  was C:/Users/17175 did load it as that project's local settings file. Live DB
  rows prove the hooks have run in that home-project context. The current hook
  block is therefore contextual, not a globally loaded user setting.
- The installed Claude version ignored an explicit settings file after the
  proposed UserPromptSubmit mcp_tool entry was added. With the entry absent, the
  same explicit PostToolUse capture setting ran. The script fallback is required.
- The temporary live-tree capture line was removed and the original file hash
  A0B6F36A48A1B1F5CCDB6D585179A2AEB1C96C4F40942ACE3F5D20FC34843DBE was restored.

## Verification independence

Builder: Codex. Auditor: Claude Opus. Author not in verifiers.
