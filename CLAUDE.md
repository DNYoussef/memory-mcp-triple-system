## Memory recall and save nudges

The first Write/Edit/NotebookEdit attempt each prompt is denied until a real
unified_search / context_retrieve / hipporag_retrieve call succeeds this prompt.
The edit denial is one-shot to prevent a hook deadlock if memory is unavailable. Each
session-end attempt is blocked while an edit is newer than the last memory_store save,
unless explicitly waived via
kv_set(key="skip:<session_id>", value="<reason>", ttl=86400). Load the search
tool with one ToolSearch call at task start to avoid the denial round-trip.
