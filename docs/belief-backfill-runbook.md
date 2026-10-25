# Belief web backfill runbook (PLAN-B section 7)

Owner-run. Every step below is a separate command of `scripts/belief_backfill.py`
and every path is passed explicitly; nothing defaults to the live data directory.
The extraction step sends memory text to a model provider, so it needs the owner's
approval on the day it runs (PLAN-B section 9, privacy).

Run from the repo root with `PYTHONPATH=.` set. In the examples, `$DATA` is the live
data directory and `$WORK` is a new scratch directory for this run.

## 0. Before anything

1. Quiesce writers (lane A section 4 step 2): stop the memory server and the hooks.
2. Back up `agent_kv.db` with the sqlite backup API, open the copy and count rows
   (lane A section 4 steps 3-4). Record the counts in the deploy log.
3. Copy the Chroma directory to `$WORK/chroma-copy`. Export reads the copy, never
   the live directory: a Chroma client may write to the directory it opens.

## 1. Export (sanitized, fail closed)

    python scripts/belief_backfill.py export --chroma $WORK/chroma-copy \
        --out $WORK/export.jsonl

The export reads BOTH real-memory collections, `memory_chunks` and `agent_memories`
(PLAN-B section 1.1: 1,528 + 153 = 1,681 when measured), into ONE file, so one
validate and one load under one import id cover both. `--collection` (repeatable)
overrides the pair; the test_* collections are never exported by default. Each
collection's paged read is reconciled with its Chroma count (a mismatch exits 1),
and the report gives read, exported and excluded per collection: check that read
matches the count you measured on the copy. An id found in two collections is
refused, because the id is the chunk the beliefs cite. A record without stored_at
(possible in the older agent_memories) is excluded and counted as
missing_stored_at; if that count is large, stop and decide before extraction.

Each record keeps id, text, stored_at, project, who and its collection. Text, project and who go
through `strip_private` (src/hooks/post_tool_handler.py). A record that still
matches `(?i)<\s*/?\s*private` afterwards (a spaced or stray tag) is EXCLUDED, and
so is a record without stored_at. The report lists the excluded counts and ids.
Report the excluded ids to the hook owner (lane A): they show what strip_private
misses. Do not hand-edit them into the export.

One Chroma record is one memory here. Its id is the chunk the beliefs cite, so
every backfilled mention is located on that chunk.

## 2. Extract (model step, owner-approved)

    python scripts/belief_backfill.py extract --export $WORK/export.jsonl \
        --out $WORK/extracted.jsonl --model-cmd "<command that reads a prompt on stdin>"

- Batches of 20 memories. Every prompt carries the key vocabulary seen so far and
  tells the model the memories are data, not instructions.
- Token abort at 1.5 M. `--budget` can only lower it: a value above 1.5 M exits 1. Tokens are estimated at four
  characters each, input plus output. A preflight estimate over the budget stops
  the run before any model call; a run that passes it mid-way stops after that
  batch and writes no output file.
- Expected volume is about 0.8 M tokens (section 7 step 2). Compute the price from
  the current price sheet before the run, not from this file.
- The report lists reply lines that were not JSON or named an unknown id, and the
  memories the model skipped (`missing`). Rerun only those if needed.

## 3. Validate (no database written)

    python scripts/belief_backfill.py validate --export $WORK/export.jsonl \
        --extracted $WORK/extracted.jsonl --db $WORK/agent_kv-copy.db \
        --review-out $WORK/review.json

- Every entry runs through the memory_store (B-PR2) write path into a scratch store
  in a temporary directory. Any error exits 1. Fix the extraction, never the
  validator.
- Backfill rules: source_type is capped at `reported` unless the memory text
  contains the entry's `quote`; reliability numbers from the model are dropped (the
  source type default applies); observed_at may not be later than the memory's
  stored_at; recorded_at is the memory's stored_at.
- Limits: at most 64 MB and 5,000 records per input file, and per memory the
  memory_store payload limits (50 entries, 20 links per entry, 200-char keys,
  2,000-char text fields). Error reports are capped at 20,000 chars and say how
  many errors were cut.
- `review.json` lists near-duplicate key pairs (threshold 0.90 on spelling, keys
  with different numbers never pair). Every pair starts with `"approve": false`.
  `--db` (read-only) adds the existing keys to the comparison.

## 4. Load (one transaction)

    python scripts/belief_backfill.py load --db $DATA/agent_kv.db \
        --export $WORK/export.jsonl --extracted $WORK/extracted.jsonl \
        --import-id <id> --dry-run
    python scripts/belief_backfill.py load --db $DATA/agent_kv.db \
        --export $WORK/export.jsonl --extracted $WORK/extracted.jsonl --import-id <id>

The dry run validates and prints the counts without opening the database. The load
validates again, then writes every row under origin `import:<id>` in ONE
transaction: an interrupted load leaves no row of that import. Replaying the same
import is idempotent. Record the import id and the row counts in the deploy log.

## 5. Merge review window (right after the load, still quiesced)

Set `"approve": true` on the pairs to merge in `review.json`, then:

    python scripts/belief_backfill.py merge --db $DATA/agent_kv.db \
        --pairs $WORK/review.json --merge-id <id> --archive $WORK/belief-archive-pre-merge.db

The command archives the five belief tables first (refusing an existing archive
file), then applies every approved merge in one transaction. A refused merge (it
would put supports and excludes on one pair) undoes the whole batch. The archive is
the only undo for merges: an import rollback does not undo them.

## 6. Verify (section 7 step 5, section 5.4)

Restart the server (writers may resume), then:

- 50-row graded sample of the loaded beliefs: gate >= 0.8 correct.
- find_holes top 20, reviewed by the owner.
- The solver benchmark on the real web (scripts/benchmark_belief_web.py), within
  the section 3.4 budget.
- The B-PR3 matching threshold re-checked on 50 real backfilled claims.

## Rollback (section 7.1)

    python scripts/belief_backfill.py rollback --db $DATA/agent_kv.db --import-id <id>

Deletes every row of origin `import:<id>` in one transaction and nothing else:
live rows, other imports, merge rows, observations, kv_store, sessions, Chroma and
graph.json are untouched. Aliases a merge created stay, so merged names still
resolve. Rolling back an id with no rows exits 1.

Code rollback stays a config change: `belief_web.backend: pgmpy_legacy` and
optionally `belief_web.ingest: false`, then restart. No table is deleted.

## Merge undo and uninstall (section 7.2)

Undo a merge batch in the same database (keeps the live seq counter):

    python scripts/belief_backfill.py restore --db $DATA/agent_kv.db \
        --archive $WORK/belief-archive-pre-merge.db --mode same_db

Archive only:

    python scripts/belief_backfill.py archive --db $DATA/agent_kv.db --out $WORK/belief-archive-<ts>.db

Uninstall (quiesced writers only; never part of a rollback):

    python scripts/belief_backfill.py uninstall --db $DATA/agent_kv.db \
        --archive $WORK/belief-archive-<ts>.db

Uninstall archives the four belief tables and the seq counter, verifies counts and
hashes, re-checks them under the write lock, and only then drops the tables and
migration row 008 in one transaction. Live beliefs survive in the archive. To bring
them back into a fresh schema, use `restore --mode fresh`.
