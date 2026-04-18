# <span data-proof="authored" data-by="ai:claude">ideahub-mcp v0.2.0 — Writeback Spec Phase 1 Implementation Plan</span>

> **<span data-proof="authored" data-by="ai:claude">For Claude:</span>** <span data-proof="authored" data-by="ai:claude">REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.</span>

**<span data-proof="authored" data-by="ai:claude">Goal:</span>** <span data-proof="authored" data-by="ai:claude">Make</span> <span data-proof="authored" data-by="ai:claude">`ideahub-mcp`</span> <span data-proof="authored" data-by="ai:claude">feel like working memory by adding a second write verb (`checkpoint`), uniform</span> <span data-proof="authored" data-by="ai:claude">`task_ref`</span> <span data-proof="authored" data-by="ai:claude">provenance across all four write-path verbs, and candidate-surfacing return payloads so the model sees where a trace likely belongs without being told what to do.</span>

**<span data-proof="authored" data-by="ai:claude">Architecture:</span>** <span data-proof="authored" data-by="ai:claude">Single SQLite migration adds</span> <span data-proof="authored" data-by="ai:claude">`kind`</span> <span data-proof="authored" data-by="ai:claude">and</span> <span data-proof="authored" data-by="ai:claude">`task_ref`</span> <span data-proof="authored" data-by="ai:claude">columns. All four write-path tools (`capture`,</span> <span data-proof="authored" data-by="ai:claude">`checkpoint`,</span> <span data-proof="authored" data-by="ai:claude">`annotate`,</span> <span data-proof="authored" data-by="ai:claude">`link`) accept an optional</span> <span data-proof="authored" data-by="ai:claude">`task_ref`. A new shared scorer produces</span> <span data-proof="authored" data-by="ai:claude">`annotate_candidates`</span> <span data-proof="authored" data-by="ai:claude">and</span> <span data-proof="authored" data-by="ai:claude">`related_candidates`</span> <span data-proof="authored" data-by="ai:claude">at write time, ranked by FTS → shared task_ref → shared originator → recency. Top-level search/list/dump default-exclude</span> <span data-proof="authored" data-by="ai:claude">`kind='checkpoint'`</span> <span data-proof="authored" data-by="ai:claude">(opt-in via</span> <span data-proof="authored" data-by="ai:claude">`include_checkpoints`).</span> <span data-proof="authored" data-by="ai:claude">`related_ideas`</span> <span data-proof="authored" data-by="ai:claude">scoring is untouched in v0.2.0 (flagged for later).</span>

**<span data-proof="authored" data-by="ai:claude">Tech Stack:</span>** <span data-proof="authored" data-by="ai:claude">Python 3.13, FastMCP 2.x, native</span> <span data-proof="authored" data-by="ai:claude">`sqlite3`</span> <span data-proof="authored" data-by="ai:claude">with FTS5, Pydantic 2, pytest + pytest-asyncio + hypothesis, ruff + pyright.</span>

***

## <span data-proof="authored" data-by="ai:claude">Context Before Starting</span>

<span data-proof="authored" data-by="ai:claude">Read these files before beginning. They are the load-bearing prior art:</span>

* <span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/tools/capture.py`</span> <span data-proof="authored" data-by="ai:claude">— existing write shape, dedup window,</span> <span data-proof="authored" data-by="ai:claude">`_suggest_tags`</span>

* <span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/tools/annotate.py`</span> <span data-proof="authored" data-by="ai:claude">— existing note-append shape</span>

* <span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/tools/link.py`</span> <span data-proof="authored" data-by="ai:claude">— existing link canonicalization + idempotency</span>

* <span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/tools/related.py`</span> <span data-proof="authored" data-by="ai:claude">— existing scorer (tag overlap → shared_originator → recency);</span> **<span data-proof="authored" data-by="ai:claude">do not modify in v0.2.0</span>**

* <span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/tools/search.py`</span> <span data-proof="authored" data-by="ai:claude">— existing FTS5 query shape</span>

* <span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/tools/list_ideas.py`,</span> <span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/tools/dump.py`</span> <span data-proof="authored" data-by="ai:claude">— existing filters</span>

* <span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/server.py`</span> <span data-proof="authored" data-by="ai:claude">— how tools are registered and wired</span>

* <span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/storage/migrations/001_init.sql`</span> <span data-proof="authored" data-by="ai:claude">— current schema</span>

* <span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/storage/migrations.py`</span> <span data-proof="authored" data-by="ai:claude">— migration runner (lexical order, idempotent)</span>

* <span data-proof="authored" data-by="ai:claude">`tests/conftest.py`</span> <span data-proof="authored" data-by="ai:claude">—</span> <span data-proof="authored" data-by="ai:claude">`conn`</span> <span data-proof="authored" data-by="ai:claude">fixture gives a fresh migrated SQLite;</span> <span data-proof="authored" data-by="ai:claude">`tmp_home`</span> <span data-proof="authored" data-by="ai:claude">isolates</span> <span data-proof="authored" data-by="ai:claude">`IDEAHUB_MCP_HOME`</span>

**<span data-proof="authored" data-by="ai:claude">Design decisions already made (do not re-open):</span>**

* <span data-proof="authored" data-by="ai:claude">Same-table storage: checkpoints live in</span> <span data-proof="authored" data-by="ai:claude">`idea`</span> <span data-proof="authored" data-by="ai:claude">with</span> <span data-proof="authored" data-by="ai:claude">`kind='checkpoint'`.</span>

* <span data-proof="authored" data-by="ai:claude">`task_ref`</span> <span data-proof="authored" data-by="ai:claude">is an opaque free-form string, no validation, no lifecycle.</span>

* <span data-proof="authored" data-by="ai:claude">`related_ideas`</span> <span data-proof="authored" data-by="ai:claude">scorer is</span> **<span data-proof="authored" data-by="ai:claude">not</span>** <span data-proof="authored" data-by="ai:claude">touched in v0.2.0 — only top-level search/list/dump default-exclude checkpoints.</span>

* <span data-proof="authored" data-by="ai:claude">Scoring ladder for write-time candidates: FTS/bm25 → shared</span> <span data-proof="authored" data-by="ai:claude">`task_ref`</span> <span data-proof="authored" data-by="ai:claude">→ shared originator → recency.</span>

* <span data-proof="authored" data-by="ai:claude">Return-payload signals are structured facts,</span> **<span data-proof="authored" data-by="ai:claude">not</span>** <span data-proof="authored" data-by="ai:claude">imperative action strings.</span>

**<span data-proof="authored" data-by="ai:claude">Out of scope for v0.2.0:</span>**

* <span data-proof="authored" data-by="ai:claude">`promote`</span> <span data-proof="authored" data-by="ai:claude">tool</span>

* <span data-proof="authored" data-by="ai:claude">`start_task`</span> <span data-proof="authored" data-by="ai:claude">/</span> <span data-proof="authored" data-by="ai:claude">`finish_task`</span> <span data-proof="authored" data-by="ai:claude">lifecycle tools</span>

* <span data-proof="authored" data-by="ai:claude">Kind-aware tweak to</span> <span data-proof="authored" data-by="ai:claude">`related_ideas`</span> <span data-proof="authored" data-by="ai:claude">scorer</span>

* <span data-proof="authored" data-by="ai:claude">`memory_loop`</span> <span data-proof="authored" data-by="ai:claude">prompt or</span> <span data-proof="authored" data-by="ai:claude">`ideahub://working-memory-policy`</span> <span data-proof="authored" data-by="ai:claude">resource</span>

* <span data-proof="authored" data-by="ai:claude">Elicitation on weak writes</span>

* <span data-proof="authored" data-by="ai:claude">Extended</span> <span data-proof="authored" data-by="ai:claude">`ping`</span> <span data-proof="authored" data-by="ai:claude">/</span> <span data-proof="authored" data-by="ai:claude">`current_context`</span>

***

## <span data-proof="authored" data-by="ai:claude">Task 1: Schema Migration (kind + task_ref columns)</span>

**<span data-proof="authored" data-by="ai:claude">Files:</span>**

* <span data-proof="authored" data-by="ai:claude">Create:</span> <span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/storage/migrations/002_kind_and_task_ref.sql`</span>

* <span data-proof="authored" data-by="ai:claude">Test:</span> <span data-proof="authored" data-by="ai:claude">`tests/test_migrations.py`</span> <span data-proof="authored" data-by="ai:claude">(add new test)</span>

**<span data-proof="authored" data-by="ai:claude">Step 1: Write the failing test</span>**

<span data-proof="authored" data-by="ai:claude">Append to</span> <span data-proof="authored" data-by="ai:claude">`tests/test_migrations.py`:</span>

```python proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MTE3MSwiYXR0cnMiOnsiYnkiOiJhaTpjbGF1ZGUifX1d
def test_migration_002_adds_kind_and_task_ref(conn: sqlite3.Connection) -> None:
    idea_cols = {r[1] for r in conn.execute("PRAGMA table_info(idea)").fetchall()}
    assert "kind" in idea_cols
    assert "task_ref" in idea_cols

    note_cols = {r[1] for r in conn.execute("PRAGMA table_info(idea_note)").fetchall()}
    assert "task_ref" in note_cols

    link_cols = {r[1] for r in conn.execute("PRAGMA table_info(idea_link)").fetchall()}
    assert "task_ref" in link_cols

    # Default for idea.kind is 'idea'
    conn.execute(
        "INSERT INTO actor (id, kind, display_name, first_seen_at) "
        "VALUES ('a1','agent','a1',datetime('now'))"
    )
    conn.execute(
        "INSERT INTO idea (id, content, scope, actor_id, tags, created_at) "
        "VALUES ('i1','x','s','a1','[]',datetime('now'))"
    )
    row = conn.execute("SELECT kind, task_ref FROM idea WHERE id='i1'").fetchone()
    assert row[0] == "idea"
    assert row[1] is None

    # Index present
    idxs = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
    ).fetchall()}
    assert "idea_kind_idx" in idxs
    assert "idea_task_ref_idx" in idxs
```

**<span data-proof="authored" data-by="ai:claude">Step 2: Run the test to verify it fails</span>**

<span data-proof="authored" data-by="ai:claude">Run:</span> <span data-proof="authored" data-by="ai:claude">`uv run pytest tests/test_migrations.py::test_migration_002_adds_kind_and_task_ref -v`
Expected: FAIL — migration file does not exist;</span> <span data-proof="authored" data-by="ai:claude">`kind`</span> <span data-proof="authored" data-by="ai:claude">and</span> <span data-proof="authored" data-by="ai:claude">`task_ref`</span> <span data-proof="authored" data-by="ai:claude">columns absent.</span>

**<span data-proof="authored" data-by="ai:claude">Step 3: Write the migration</span>**

<span data-proof="authored" data-by="ai:claude">Create</span> <span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/storage/migrations/002_kind_and_task_ref.sql`:</span>

```sql proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MzY4LCJhdHRycyI6eyJieSI6ImFpOmNsYXVkZSJ9fV0=
ALTER TABLE idea ADD COLUMN kind TEXT NOT NULL DEFAULT 'idea'
  CHECK (kind IN ('idea','checkpoint'));
ALTER TABLE idea ADD COLUMN task_ref TEXT;

ALTER TABLE idea_note ADD COLUMN task_ref TEXT;
ALTER TABLE idea_link ADD COLUMN task_ref TEXT;

CREATE INDEX idea_kind_idx     ON idea (kind);
CREATE INDEX idea_task_ref_idx ON idea (task_ref) WHERE task_ref IS NOT NULL;
```

**<span data-proof="authored" data-by="ai:claude">Step 4: Run the test to verify it passes</span>**

<span data-proof="authored" data-by="ai:claude">Run:</span> <span data-proof="authored" data-by="ai:claude">`uv run pytest tests/test_migrations.py -v`
Expected: all migration tests PASS.</span>

**<span data-proof="authored" data-by="ai:claude">Step 5: Run full suite to confirm no regressions</span>**

<span data-proof="authored" data-by="ai:claude">Run:</span> <span data-proof="authored" data-by="ai:claude">`uv run pytest -q`
Expected: all existing tests PASS (the new columns are optional and defaulted).</span>

**<span data-proof="authored" data-by="ai:claude">Step 6: Commit</span>**

```bash proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MzI5LCJhdHRycyI6eyJieSI6ImFpOmNsYXVkZSJ9fV0=
git add src/ideahub_mcp/storage/migrations/002_kind_and_task_ref.sql tests/test_migrations.py
git commit -m "$(cat <<'EOF'
Add kind and task_ref columns so the ideas table can carry checkpoints and provenance back to the task that produced any mutation

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

***

## <span data-proof="authored" data-by="ai:claude">Task 2: Thread task_ref through capture</span>

**<span data-proof="authored" data-by="ai:claude">Files:</span>**

* <span data-proof="authored" data-by="ai:claude">Modify:</span> <span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/tools/capture.py`</span>

* <span data-proof="authored" data-by="ai:claude">Test:</span> <span data-proof="authored" data-by="ai:claude">`tests/test_capture.py`</span> <span data-proof="authored" data-by="ai:claude">(add new test)</span>

**<span data-proof="authored" data-by="ai:claude">Step 1: Write the failing test</span>**

<span data-proof="authored" data-by="ai:claude">Append to</span> <span data-proof="authored" data-by="ai:claude">`tests/test_capture.py`:</span>

```python proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6ODMwLCJhdHRycyI6eyJieSI6ImFpOmNsYXVkZSJ9fV0=
def test_capture_persists_task_ref(conn: sqlite3.Connection, seeded_actor: str) -> None:
    out = capture_idea(
        conn,
        CaptureInput(
            content="mid-task observation",
            scope="s1",
            actor=seeded_actor,
            task_ref="writeback-phase-1",
        ),
    )
    row = conn.execute("SELECT task_ref FROM idea WHERE id = ?", (out.id,)).fetchone()
    assert row[0] == "writeback-phase-1"
    assert out.task_ref == "writeback-phase-1"


def test_capture_task_ref_is_optional(conn: sqlite3.Connection, seeded_actor: str) -> None:
    out = capture_idea(
        conn, CaptureInput(content="anything", scope="s1", actor=seeded_actor)
    )
    row = conn.execute("SELECT task_ref FROM idea WHERE id = ?", (out.id,)).fetchone()
    assert row[0] is None
    assert out.task_ref is None
```

<span data-proof="authored" data-by="ai:claude">(If</span> <span data-proof="authored" data-by="ai:claude">`seeded_actor`</span> <span data-proof="authored" data-by="ai:claude">fixture doesn't exist, check the top of</span> <span data-proof="authored" data-by="ai:claude">`tests/test_capture.py`</span> <span data-proof="authored" data-by="ai:claude">for the existing pattern and replicate it. Use whatever actor-seeding pattern the other tests already use.)</span>

**<span data-proof="authored" data-by="ai:claude">Step 2: Run the tests to verify they fail</span>**

<span data-proof="authored" data-by="ai:claude">Run:</span> <span data-proof="authored" data-by="ai:claude">`uv run pytest tests/test_capture.py::test_capture_persists_task_ref tests/test_capture.py::test_capture_task_ref_is_optional -v`
Expected: FAIL —</span> <span data-proof="authored" data-by="ai:claude">`CaptureInput`</span> <span data-proof="authored" data-by="ai:claude">has no</span> <span data-proof="authored" data-by="ai:claude">`task_ref`</span> <span data-proof="authored" data-by="ai:claude">field;</span> <span data-proof="authored" data-by="ai:claude">`CaptureOutput`</span> <span data-proof="authored" data-by="ai:claude">has no</span> <span data-proof="authored" data-by="ai:claude">`task_ref`</span> <span data-proof="authored" data-by="ai:claude">field.</span>

**<span data-proof="authored" data-by="ai:claude">Step 3: Update</span>** **<span data-proof="authored" data-by="ai:claude">`CaptureInput`,</span>** **<span data-proof="authored" data-by="ai:claude">`CaptureOutput`, and persistence</span>**

<span data-proof="authored" data-by="ai:claude">In</span> <span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/tools/capture.py`:</span>

1. <span data-proof="authored" data-by="ai:claude">Add</span> <span data-proof="authored" data-by="ai:claude">`task_ref: str | None = None`</span> <span data-proof="authored" data-by="ai:claude">to</span> <span data-proof="authored" data-by="ai:claude">`CaptureInput`</span> <span data-proof="authored" data-by="ai:claude">(after</span> <span data-proof="authored" data-by="ai:claude">`actor_created`).</span>
2. <span data-proof="authored" data-by="ai:claude">Add</span> <span data-proof="authored" data-by="ai:claude">`task_ref: str | None = None`</span> <span data-proof="authored" data-by="ai:claude">to</span> <span data-proof="authored" data-by="ai:claude">`CaptureOutput`.</span>
3. <span data-proof="authored" data-by="ai:claude">Update the dedup-return</span> <span data-proof="authored" data-by="ai:claude">`CaptureOutput(...)`</span> <span data-proof="authored" data-by="ai:claude">to pass</span> <span data-proof="authored" data-by="ai:claude">`task_ref=input_.task_ref`.</span>
4. <span data-proof="authored" data-by="ai:claude">Update the INSERT to include</span> <span data-proof="authored" data-by="ai:claude">`task_ref`:</span>

```python proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MzQ3LCJhdHRycyI6eyJieSI6ImFpOmNsYXVkZSJ9fV0=
conn.execute(
    "INSERT INTO idea (id, content, scope, actor_id, originator_id, tags, created_at, task_ref) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
    (
        new_id,
        input_.content,
        input_.scope,
        input_.actor,
        input_.originator,
        json.dumps(input_.tags),
        now,
        input_.task_ref,
    ),
)
```

1. <span data-proof="authored" data-by="ai:claude">Update the final-return</span> <span data-proof="authored" data-by="ai:claude">`CaptureOutput(...)`</span> <span data-proof="authored" data-by="ai:claude">to pass</span> <span data-proof="authored" data-by="ai:claude">`task_ref=input_.task_ref`.</span>

**<span data-proof="authored" data-by="ai:claude">Step 4: Run tests to verify they pass</span>**

<span data-proof="authored" data-by="ai:claude">Run:</span> <span data-proof="authored" data-by="ai:claude">`uv run pytest tests/test_capture.py -v`
Expected: all capture tests PASS.</span>

**<span data-proof="authored" data-by="ai:claude">Step 5: Commit</span>**

```bash proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MjgxLCJhdHRycyI6eyJieSI6ImFpOmNsYXVkZSJ9fV0=
git add src/ideahub_mcp/tools/capture.py tests/test_capture.py
git commit -m "$(cat <<'EOF'
Thread an optional task_ref through capture so durable ideas can carry the anchor of the task that produced them

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

***

## <span data-proof="authored" data-by="ai:claude">Task 3: Thread task_ref through annotate</span>

**<span data-proof="authored" data-by="ai:claude">Files:</span>**

* <span data-proof="authored" data-by="ai:claude">Modify:</span> <span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/tools/annotate.py`</span>

* <span data-proof="authored" data-by="ai:claude">Test:</span> <span data-proof="authored" data-by="ai:claude">`tests/test_annotate.py`</span> <span data-proof="authored" data-by="ai:claude">(add new test)</span>

**<span data-proof="authored" data-by="ai:claude">Step 1: Write the failing test</span>**

<span data-proof="authored" data-by="ai:claude">Append to</span> <span data-proof="authored" data-by="ai:claude">`tests/test_annotate.py`:</span>

```python proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6NTI3LCJhdHRycyI6eyJieSI6ImFpOmNsYXVkZSJ9fV0=
def test_annotate_persists_task_ref(conn: sqlite3.Connection, seeded_idea_id: str, seeded_actor: str) -> None:
    out = annotate_idea(
        conn,
        AnnotateInput(
            id=seeded_idea_id,
            content="correction",
            actor=seeded_actor,
            task_ref="writeback-phase-1",
        ),
    )
    row = conn.execute(
        "SELECT task_ref FROM idea_note WHERE id = ?", (out.note_id,)
    ).fetchone()
    assert row[0] == "writeback-phase-1"
    assert out.task_ref == "writeback-phase-1"
```

<span data-proof="authored" data-by="ai:claude">(Reuse whatever</span> <span data-proof="authored" data-by="ai:claude">`seeded_idea_id`</span> <span data-proof="authored" data-by="ai:claude">/</span> <span data-proof="authored" data-by="ai:claude">`seeded_actor`</span> <span data-proof="authored" data-by="ai:claude">fixture pattern already exists in that test file.)</span>

**<span data-proof="authored" data-by="ai:claude">Step 2: Run the test to verify it fails</span>**

<span data-proof="authored" data-by="ai:claude">Run:</span> <span data-proof="authored" data-by="ai:claude">`uv run pytest tests/test_annotate.py::test_annotate_persists_task_ref -v`
Expected: FAIL —</span> <span data-proof="authored" data-by="ai:claude">`AnnotateInput`</span> <span data-proof="authored" data-by="ai:claude">has no</span> <span data-proof="authored" data-by="ai:claude">`task_ref`.</span>

**<span data-proof="authored" data-by="ai:claude">Step 3: Update annotate.py</span>**

<span data-proof="authored" data-by="ai:claude">In</span> <span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/tools/annotate.py`:</span>

1. <span data-proof="authored" data-by="ai:claude">Add</span> <span data-proof="authored" data-by="ai:claude">`task_ref: str | None = None`</span> <span data-proof="authored" data-by="ai:claude">to</span> <span data-proof="authored" data-by="ai:claude">`AnnotateInput`.</span>
2. <span data-proof="authored" data-by="ai:claude">Add</span> <span data-proof="authored" data-by="ai:claude">`task_ref: str | None = None`</span> <span data-proof="authored" data-by="ai:claude">to</span> <span data-proof="authored" data-by="ai:claude">`AnnotateOutput`.</span>
3. <span data-proof="authored" data-by="ai:claude">Update the INSERT:</span>

```python proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MzQ3LCJhdHRycyI6eyJieSI6ImFpOmNsYXVkZSJ9fV0=
conn.execute(
    "INSERT INTO idea_note "
    "(id, idea_id, kind, content, actor_id, originator_id, created_at, task_ref) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
    (
        note_id,
        input_.id,
        input_.kind,
        input_.content,
        input_.actor,
        input_.originator,
        now,
        input_.task_ref,
    ),
)
```

1. <span data-proof="authored" data-by="ai:claude">Update the return:</span>

```python proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MTQwLCJhdHRycyI6eyJieSI6ImFpOmNsYXVkZSJ9fV0=
return AnnotateOutput(
    note_id=note_id,
    idea_id=input_.id,
    kind=input_.kind,
    created_at=now,
    task_ref=input_.task_ref,
)
```

**<span data-proof="authored" data-by="ai:claude">Step 4: Run tests to verify they pass</span>**

<span data-proof="authored" data-by="ai:claude">Run:</span> <span data-proof="authored" data-by="ai:claude">`uv run pytest tests/test_annotate.py -v`
Expected: PASS.</span>

**<span data-proof="authored" data-by="ai:claude">Step 5: Commit</span>**

```bash proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6Mjk0LCJhdHRycyI6eyJieSI6ImFpOmNsYXVkZSJ9fV0=
git add src/ideahub_mcp/tools/annotate.py tests/test_annotate.py
git commit -m "$(cat <<'EOF'
Thread an optional task_ref through annotate so notes on existing ideas reconstruct into the task stream that produced them

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

***

## <span data-proof="authored" data-by="ai:claude">Task 4: Thread task_ref through link</span>

**<span data-proof="authored" data-by="ai:claude">Files:</span>**

* <span data-proof="authored" data-by="ai:claude">Modify:</span> <span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/tools/link.py`</span>

* <span data-proof="authored" data-by="ai:claude">Test:</span> <span data-proof="authored" data-by="ai:claude">`tests/test_link.py`</span> <span data-proof="authored" data-by="ai:claude">(add new test)</span>

**<span data-proof="authored" data-by="ai:claude">Step 1: Write the failing test</span>**

<span data-proof="authored" data-by="ai:claude">Append to</span> <span data-proof="authored" data-by="ai:claude">`tests/test_link.py`:</span>

```python proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MTM1NywiYXR0cnMiOnsiYnkiOiJhaTpjbGF1ZGUifX1d
def test_link_persists_task_ref(conn: sqlite3.Connection, two_seeded_idea_ids: tuple[str, str]) -> None:
    src, tgt = two_seeded_idea_ids
    out = link_ideas(
        conn,
        LinkInput(
            source_id=src,
            target_id=tgt,
            kind="related",
            task_ref="writeback-phase-1",
        ),
    )
    row = conn.execute(
        "SELECT task_ref FROM idea_link "
        "WHERE source_idea_id = ? AND target_idea_id = ? AND kind = ?",
        (out.source_id, out.target_id, out.kind),
    ).fetchone()
    assert row[0] == "writeback-phase-1"
    assert out.task_ref == "writeback-phase-1"


def test_link_idempotency_preserves_first_task_ref(
    conn: sqlite3.Connection, two_seeded_idea_ids: tuple[str, str]
) -> None:
    src, tgt = two_seeded_idea_ids
    link_ideas(conn, LinkInput(source_id=src, target_id=tgt, kind="related", task_ref="first"))
    second = link_ideas(
        conn, LinkInput(source_id=src, target_id=tgt, kind="related", task_ref="second")
    )
    assert second.created is False
    # First task_ref wins; the idempotent no-op does not overwrite.
    row = conn.execute(
        "SELECT task_ref FROM idea_link "
        "WHERE source_idea_id = ? AND target_idea_id = ? AND kind = ?",
        (second.source_id, second.target_id, second.kind),
    ).fetchone()
    assert row[0] == "first"
```

<span data-proof="authored" data-by="ai:claude">(Again, reuse the existing fixture pattern for seeding two ideas.)</span>

**<span data-proof="authored" data-by="ai:claude">Step 2: Run the tests to verify they fail</span>**

<span data-proof="authored" data-by="ai:claude">Run:</span> <span data-proof="authored" data-by="ai:claude">`uv run pytest tests/test_link.py::test_link_persists_task_ref -v`
Expected: FAIL.</span>

**<span data-proof="authored" data-by="ai:claude">Step 3: Update link.py</span>**

<span data-proof="authored" data-by="ai:claude">In</span> <span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/tools/link.py`:</span>

1. <span data-proof="authored" data-by="ai:claude">Add</span> <span data-proof="authored" data-by="ai:claude">`task_ref: str | None = None`</span> <span data-proof="authored" data-by="ai:claude">to</span> <span data-proof="authored" data-by="ai:claude">`LinkInput`.</span>
2. <span data-proof="authored" data-by="ai:claude">Add</span> <span data-proof="authored" data-by="ai:claude">`task_ref: str | None = None`</span> <span data-proof="authored" data-by="ai:claude">to</span> <span data-proof="authored" data-by="ai:claude">`LinkOutput`.</span>
3. <span data-proof="authored" data-by="ai:claude">On idempotent hit, read the existing</span> <span data-proof="authored" data-by="ai:claude">`task_ref`</span> <span data-proof="authored" data-by="ai:claude">and return it:</span>

```python proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MzE1LCJhdHRycyI6eyJieSI6ImFpOmNsYXVkZSJ9fV0=
existing = conn.execute(
    "SELECT task_ref FROM idea_link "
    "WHERE source_idea_id = ? AND target_idea_id = ? AND kind = ?",
    (src, tgt, input_.kind),
).fetchone()
if existing:
    return LinkOutput(
        source_id=src, target_id=tgt, kind=input_.kind,
        created=False, task_ref=existing[0],
    )
```

1. <span data-proof="authored" data-by="ai:claude">On fresh insert, persist and return the incoming</span> <span data-proof="authored" data-by="ai:claude">`task_ref`:</span>

```python proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MzEyLCJhdHRycyI6eyJieSI6ImFpOmNsYXVkZSJ9fV0=
conn.execute(
    "INSERT INTO idea_link (source_idea_id, target_idea_id, kind, created_at, task_ref) "
    "VALUES (?, ?, ?, ?, ?)",
    (src, tgt, input_.kind, utcnow_iso(), input_.task_ref),
)
return LinkOutput(
    source_id=src, target_id=tgt, kind=input_.kind,
    created=True, task_ref=input_.task_ref,
)
```

**<span data-proof="authored" data-by="ai:claude">Step 4: Run tests to verify they pass</span>**

<span data-proof="authored" data-by="ai:claude">Run:</span> <span data-proof="authored" data-by="ai:claude">`uv run pytest tests/test_link.py -v`
Expected: PASS.</span>

**<span data-proof="authored" data-by="ai:claude">Step 5: Commit</span>**

```bash proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MzMwLCJhdHRycyI6eyJieSI6ImFpOmNsYXVkZSJ9fV0=
git add src/ideahub_mcp/tools/link.py tests/test_link.py
git commit -m "$(cat <<'EOF'
Thread an optional task_ref through link so graph mutations can be traced to the task that revealed the relationship; preserve the first task_ref on idempotent repeats

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

***

## <span data-proof="authored" data-by="ai:claude">Task 5: New checkpoint tool</span>

**<span data-proof="authored" data-by="ai:claude">Files:</span>**

* <span data-proof="authored" data-by="ai:claude">Create:</span> <span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/tools/checkpoint.py`</span>

* <span data-proof="authored" data-by="ai:claude">Create:</span> <span data-proof="authored" data-by="ai:claude">`tests/test_checkpoint.py`</span>

**<span data-proof="authored" data-by="ai:claude">Step 1: Write the failing tests</span>**

<span data-proof="authored" data-by="ai:claude">Create</span> <span data-proof="authored" data-by="ai:claude">`tests/test_checkpoint.py`:</span>

```python proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MTg0MywiYXR0cnMiOnsiYnkiOiJhaTpjbGF1ZGUifX1d
from __future__ import annotations

import sqlite3

import pytest

from ideahub_mcp.tools.checkpoint import CheckpointInput, checkpoint_idea


@pytest.fixture
def seeded_actor(conn: sqlite3.Connection) -> str:
    conn.execute(
        "INSERT INTO actor (id, kind, display_name, first_seen_at) "
        "VALUES ('a1','agent','a1',datetime('now'))"
    )
    return "a1"


def test_checkpoint_writes_row_with_kind_checkpoint(
    conn: sqlite3.Connection, seeded_actor: str
) -> None:
    out = checkpoint_idea(
        conn,
        CheckpointInput(
            content="assumption: the scorer should weight FTS first",
            scope="s1",
            actor=seeded_actor,
            task_ref="writeback-phase-1",
            kind_label="assumption",
        ),
    )
    row = conn.execute(
        "SELECT kind, task_ref, content FROM idea WHERE id = ?", (out.id,)
    ).fetchone()
    assert row[0] == "checkpoint"
    assert row[1] == "writeback-phase-1"
    assert row[2] == "[assumption] assumption: the scorer should weight FTS first"
    assert out.kind == "checkpoint"
    assert out.task_ref == "writeback-phase-1"


def test_checkpoint_accepts_tags(
    conn: sqlite3.Connection, seeded_actor: str
) -> None:
    out = checkpoint_idea(
        conn,
        CheckpointInput(
            content="x",
            scope="s1",
            actor=seeded_actor,
            tags=["scorer", "phase-1"],
        ),
    )
    import json
    row = conn.execute("SELECT tags FROM idea WHERE id = ?", (out.id,)).fetchone()
    assert set(json.loads(row[0])) == {"scorer", "phase-1"}


def test_checkpoint_task_ref_optional(
    conn: sqlite3.Connection, seeded_actor: str
) -> None:
    out = checkpoint_idea(
        conn,
        CheckpointInput(content="drive-by observation", scope="s1", actor=seeded_actor),
    )
    assert out.task_ref is None
```

**<span data-proof="authored" data-by="ai:claude">Step 2: Run the tests to verify they fail</span>**

<span data-proof="authored" data-by="ai:claude">Run:</span> <span data-proof="authored" data-by="ai:claude">`uv run pytest tests/test_checkpoint.py -v`
Expected: FAIL —</span> <span data-proof="authored" data-by="ai:claude">`ideahub_mcp.tools.checkpoint`</span> <span data-proof="authored" data-by="ai:claude">does not exist.</span>

**<span data-proof="authored" data-by="ai:claude">Step 3: Write</span>** **<span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/tools/checkpoint.py`</span>**

```python proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MjY0NiwiYXR0cnMiOnsiYnkiOiJhaTpjbGF1ZGUifX1d
from __future__ import annotations

import json
import sqlite3

from pydantic import BaseModel, Field, field_validator

from ideahub_mcp.util.clock import utcnow_iso
from ideahub_mcp.util.coerce import coerce_str_list
from ideahub_mcp.util.ids import new_ulid


class CheckpointInput(BaseModel):
    content: str = Field(..., min_length=1)
    scope: str
    actor: str
    originator: str | None = None
    tags: list[str] = Field(default_factory=list)
    task_ref: str | None = None
    kind_label: str | None = None  # semantic hint: observation, decision, assumption, ...
    actor_created: bool = False

    @field_validator("tags", mode="before")
    @classmethod
    def _coerce_tags(cls, v: object) -> list[str]:
        return coerce_str_list(v)


class CheckpointOutput(BaseModel):
    id: str
    kind: str
    scope: str
    actor: str
    originator: str | None
    created_at: str
    task_ref: str | None
    suggested_tags: list[str]
    actor_created: bool = False


def _suggest_tags(conn: sqlite3.Connection, content: str, limit: int = 5) -> list[str]:
    rows = conn.execute("SELECT tags FROM idea WHERE tags != '[]'").fetchall()
    known: set[str] = set()
    for (tags_json,) in rows:
        try:
            known.update(json.loads(tags_json))
        except json.JSONDecodeError:
            continue
    lowered = content.lower()
    return sorted([t for t in known if t.lower() in lowered])[:limit]


def checkpoint_idea(conn: sqlite3.Connection, input_: CheckpointInput) -> CheckpointOutput:
    new_id = new_ulid()
    now = utcnow_iso()

    # Fold the semantic label into the stored content so it remains searchable
    # without adding a new column; the label is a display hint, not a schema
    # commitment.
    stored_content = input_.content
    if input_.kind_label:
        stored_content = f"[{input_.kind_label}] {input_.content}"

    conn.execute(
        "INSERT INTO idea "
        "(id, content, scope, actor_id, originator_id, tags, created_at, kind, task_ref) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 'checkpoint', ?)",
        (
            new_id,
            stored_content,
            input_.scope,
            input_.actor,
            input_.originator,
            json.dumps(input_.tags),
            now,
            input_.task_ref,
        ),
    )
    return CheckpointOutput(
        id=new_id,
        kind="checkpoint",
        scope=input_.scope,
        actor=input_.actor,
        originator=input_.originator,
        created_at=now,
        task_ref=input_.task_ref,
        suggested_tags=_suggest_tags(conn, input_.content),
        actor_created=input_.actor_created,
    )
```

**<span data-proof="authored" data-by="ai:claude">Step 4: Run the tests to verify they pass</span>**

<span data-proof="authored" data-by="ai:claude">Run:</span> <span data-proof="authored" data-by="ai:claude">`uv run pytest tests/test_checkpoint.py -v`
Expected: PASS.</span>

**<span data-proof="authored" data-by="ai:claude">Step 5: Commit</span>**

```bash proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MjkwLCJhdHRycyI6eyJieSI6ImFpOmNsYXVkZSJ9fV0=
git add src/ideahub_mcp/tools/checkpoint.py tests/test_checkpoint.py
git commit -m "$(cat <<'EOF'
Add a checkpoint write verb so in-flight traces have a cognitively cheap surface distinct from durable idea capture

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

***

## <span data-proof="authored" data-by="ai:claude">Task 6: Shared candidate scorer</span>

**<span data-proof="authored" data-by="ai:claude">Files:</span>**

* <span data-proof="authored" data-by="ai:claude">Create:</span> <span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/tools/candidates.py`</span>

* <span data-proof="authored" data-by="ai:claude">Create:</span> <span data-proof="authored" data-by="ai:claude">`tests/test_candidates.py`</span>

**<span data-proof="authored" data-by="ai:claude">Step 1: Write the failing tests</span>**

<span data-proof="authored" data-by="ai:claude">Create</span> <span data-proof="authored" data-by="ai:claude">`tests/test_candidates.py`:</span>

```python proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MzU4MCwiYXR0cnMiOnsiYnkiOiJhaTpjbGF1ZGUifX1d
from __future__ import annotations

import sqlite3

import pytest

from ideahub_mcp.tools.candidates import (
    CandidateItem,
    score_candidates_for_write,
)


@pytest.fixture
def seeded(conn: sqlite3.Connection) -> sqlite3.Connection:
    conn.execute(
        "INSERT INTO actor (id, kind, display_name, first_seen_at) "
        "VALUES ('a1','agent','a1',datetime('now')),"
        "       ('a2','agent','a2',datetime('now'))"
    )
    # Three ideas: lexical match, task-ref match, recency winner.
    conn.execute(
        "INSERT INTO idea (id, content, scope, actor_id, originator_id, tags, "
        "                  created_at, kind, task_ref) VALUES "
        "('i1','scorer ladder design','s1','a1','a1','[]','2026-04-10','idea', NULL),"
        "('i2','unrelated thing',     's1','a1','a2','[]','2026-04-15','idea','t-phase-1'),"
        "('i3','most recent thought', 's1','a2','a2','[]','2026-04-17','idea', NULL),"
        "('c1','sibling checkpoint',  's1','a1','a1','[]','2026-04-16','checkpoint','t-phase-1')"
    )
    conn.commit()
    # Seed FTS via triggers by re-inserting nothing; the existing INSERT triggers
    # on idea already populated idea_fts.
    return conn


def test_scorer_surfaces_lexical_match(seeded: sqlite3.Connection) -> None:
    result = score_candidates_for_write(
        seeded,
        content="scorer ladder for write time",
        scope="s1",
        originator=None,
        task_ref=None,
        max_candidates=5,
    )
    ids = [c.id for c in result.related]
    assert "i1" in ids  # lexical match wins


def test_scorer_promotes_shared_task_ref(seeded: sqlite3.Connection) -> None:
    result = score_candidates_for_write(
        seeded,
        content="drive-by note",
        scope="s1",
        originator=None,
        task_ref="t-phase-1",
        max_candidates=5,
    )
    ids = [c.id for c in result.related]
    # Sibling checkpoint + task-ref idea outrank the unrelated recency winner.
    assert ids.index("c1") < ids.index("i3") if "i3" in ids else True
    assert ids.index("i2") < ids.index("i3") if "i3" in ids else True


def test_scorer_prefers_shared_originator_on_ties(seeded: sqlite3.Connection) -> None:
    result = score_candidates_for_write(
        seeded,
        content="unrelated",
        scope="s1",
        originator="a1",
        task_ref=None,
        max_candidates=5,
    )
    # Among ideas with no lexical match and no task_ref, a1-originated outranks
    # a2-originated despite a2 being more recent.
    ids = [c.id for c in result.related]
    if "i1" in ids and "i3" in ids:
        assert ids.index("i1") < ids.index("i3")


def test_scorer_annotate_candidates_exclude_checkpoints(seeded: sqlite3.Connection) -> None:
    result = score_candidates_for_write(
        seeded,
        content="scorer ladder",
        scope="s1",
        originator=None,
        task_ref="t-phase-1",
        max_candidates=5,
    )
    # annotate_candidates only target durable ideas, never checkpoints.
    kinds = {c.kind for c in result.annotate_candidates}
    assert kinds == set() or kinds == {"idea"}
    ids = [c.id for c in result.annotate_candidates]
    assert "c1" not in ids


def test_scorer_explains_why(seeded: sqlite3.Connection) -> None:
    result = score_candidates_for_write(
        seeded,
        content="scorer ladder",
        scope="s1",
        originator="a1",
        task_ref="t-phase-1",
        max_candidates=5,
    )
    # Every returned item carries a non-empty `why` string.
    assert all(isinstance(c.why, str) and c.why for c in result.related)
```

**<span data-proof="authored" data-by="ai:claude">Step 2: Run the tests to verify they fail</span>**

<span data-proof="authored" data-by="ai:claude">Run:</span> <span data-proof="authored" data-by="ai:claude">`uv run pytest tests/test_candidates.py -v`
Expected: FAIL — module does not exist.</span>

**<span data-proof="authored" data-by="ai:claude">Step 3: Write</span>** **<span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/tools/candidates.py`</span>**

```python proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6NjEyNCwiYXR0cnMiOnsiYnkiOiJhaTpjbGF1ZGUifX1d
from __future__ import annotations

import re
import sqlite3

from pydantic import BaseModel


class CandidateItem(BaseModel):
    id: str
    kind: str
    preview: str
    score: float
    why: str
    created_at: str


class WriteCandidates(BaseModel):
    annotate_candidates: list[CandidateItem]
    related_candidates: list[CandidateItem]


def _preview(content: str) -> str:
    first = content.splitlines()[0] if content else ""
    return first[:120]


_FTS_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _fts_query(content: str) -> str:
    # bm25() requires an fts5 MATCH. Build an OR-of-tokens query so even short
    # checkpoints produce a usable query. Quote tokens to defuse fts5 syntax.
    tokens = [t for t in _FTS_TOKEN_RE.findall(content) if len(t) >= 3]
    if not tokens:
        return ""
    # Dedupe while preserving order; cap to keep queries bounded.
    seen: set[str] = set()
    unique: list[str] = []
    for t in tokens:
        low = t.lower()
        if low in seen:
            continue
        seen.add(low)
        unique.append(low)
        if len(unique) >= 20:
            break
    return " OR ".join(f'"{t}"' for t in unique)


def score_candidates_for_write(
    conn: sqlite3.Connection,
    *,
    content: str,
    scope: str,
    originator: str | None,
    task_ref: str | None,
    max_candidates: int = 5,
) -> WriteCandidates:
    """Produce annotate_candidates and related_candidates for a new write.

    Ladder: FTS bm25 match → shared task_ref → shared originator → recency.
    """
    query = _fts_query(content)

    # FTS side: everything that lexically matches, in the same scope, not archived.
    fts_rows: list[tuple[str, str, str, str | None, str, str, float]] = []
    if query:
        sql = (
            "SELECT i.id, i.content, i.kind, i.task_ref, i.originator_id, "
            "       i.created_at, bm25(idea_fts) AS score "
            "FROM idea_fts JOIN idea i ON i.rowid = idea_fts.rowid "
            "WHERE idea_fts MATCH ? AND i.scope = ? AND i.archived_at IS NULL "
            "ORDER BY score ASC LIMIT 50"
        )
        fts_rows = [
            (r[0], r[1], r[2], r[3], r[4], r[5], float(r[6]))
            for r in conn.execute(sql, (query, scope)).fetchall()
        ]

    # Non-FTS side: every in-scope idea (for task_ref / originator / recency
    # scoring when FTS misses). Bounded to keep this cheap on large corpora.
    nonfts_rows = conn.execute(
        "SELECT id, content, kind, task_ref, originator_id, created_at "
        "FROM idea WHERE scope = ? AND archived_at IS NULL "
        "ORDER BY created_at DESC LIMIT 100",
        (scope,),
    ).fetchall()

    # Merge. Lower bm25 = better; we invert so higher composite = better.
    merged: dict[str, dict[str, object]] = {}
    for r_id, r_content, r_kind, r_task, r_orig, r_created, r_score in fts_rows:
        merged[r_id] = {
            "id": r_id,
            "content": r_content,
            "kind": r_kind,
            "task_ref": r_task,
            "originator": r_orig,
            "created_at": r_created,
            "fts_score": r_score,
            "fts_hit": True,
        }
    for r in nonfts_rows:
        r_id, r_content, r_kind, r_task, r_orig, r_created = r
        if r_id in merged:
            continue
        merged[r_id] = {
            "id": r_id,
            "content": r_content,
            "kind": r_kind,
            "task_ref": r_task,
            "originator": r_orig,
            "created_at": r_created,
            "fts_score": None,
            "fts_hit": False,
        }

    def composite_key(row: dict[str, object]) -> tuple[float, int, int, str]:
        # Return a tuple such that Python's default ascending sort puts the
        # best candidate first. Lower is better in every slot.
        fts = row.get("fts_score")
        fts_rank = float(fts) if isinstance(fts, float) else 1e9
        shared_task = 0 if (task_ref and row.get("task_ref") == task_ref) else 1
        shared_orig = 0 if (originator and row.get("originator") == originator) else 1
        # Negate recency so newer (larger string) sorts first.
        created = str(row.get("created_at") or "")
        return (fts_rank, shared_task, shared_orig, _invert_ts(created))

    def build_why(row: dict[str, object]) -> str:
        parts: list[str] = []
        if row.get("fts_hit"):
            parts.append("lexical match")
        if task_ref and row.get("task_ref") == task_ref:
            parts.append("same task")
        if originator and row.get("originator") == originator:
            parts.append("shared originator")
        if not parts:
            parts.append("recent in scope")
        return " + ".join(parts)

    ranked = sorted(merged.values(), key=composite_key)

    related: list[CandidateItem] = []
    annotate: list[CandidateItem] = []
    for row in ranked:
        item = CandidateItem(
            id=str(row["id"]),
            kind=str(row["kind"]),
            preview=_preview(str(row["content"])),
            score=_display_score(row),
            why=build_why(row),
            created_at=str(row["created_at"]),
        )
        if len(related) < max_candidates:
            related.append(item)
        if row["kind"] == "idea" and len(annotate) < max_candidates:
            annotate.append(item)
        if len(related) >= max_candidates and len(annotate) >= max_candidates:
            break

    return WriteCandidates(annotate_candidates=annotate, related_candidates=related)


def _invert_ts(ts: str) -> str:
    # Invert ISO-8601 timestamp lexically: newer → smaller. Good enough for sort.
    inverted = "".join(chr(0x7E - (ord(c) - 0x20)) if 0x20 <= ord(c) <= 0x7E else c for c in ts)
    return inverted


def _display_score(row: dict[str, object]) -> float:
    # A small human-legible float. Higher is better.
    score = 0.0
    if row.get("fts_hit"):
        fts = row.get("fts_score")
        score += 10.0 + (1.0 / (1.0 + float(fts))) if isinstance(fts, float) else 10.0
    if row.get("task_ref"):
        score += 3.0
    if row.get("originator"):
        score += 1.0
    return round(score, 3)
```

**<span data-proof="authored" data-by="ai:claude">Step 4: Run the tests to verify they pass</span>**

<span data-proof="authored" data-by="ai:claude">Run:</span> <span data-proof="authored" data-by="ai:claude">`uv run pytest tests/test_candidates.py -v`
Expected: PASS.</span>

<span data-proof="authored" data-by="ai:claude">If tests fail because</span> <span data-proof="authored" data-by="ai:claude">`idea_fts`</span> <span data-proof="authored" data-by="ai:claude">isn't populated for the seeded rows, inspect the migration 001 triggers — they fire on INSERT, so the fixture should be fine. If FTS still isn't hitting, rebuild it with</span> <span data-proof="authored" data-by="ai:claude">`INSERT INTO idea_fts(idea_fts) VALUES('rebuild')`</span> <span data-proof="authored" data-by="ai:claude">in the fixture. Do not change the production triggers.</span>

**<span data-proof="authored" data-by="ai:claude">Step 5: Commit</span>**

```bash proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6Mzc1LCJhdHRycyI6eyJieSI6ImFpOmNsYXVkZSJ9fV0=
git add src/ideahub_mcp/tools/candidates.py tests/test_candidates.py
git commit -m "$(cat <<'EOF'
Produce write-time annotate and related candidates ranked by FTS, shared task_ref, shared originator, and recency so a fresh trace surfaces where it probably belongs without the model having to search

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

***

## <span data-proof="authored" data-by="ai:claude">Task 7: Enrich capture + checkpoint returns with candidates and task_context</span>

**<span data-proof="authored" data-by="ai:claude">Files:</span>**

* <span data-proof="authored" data-by="ai:claude">Modify:</span> <span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/tools/capture.py`</span>

* <span data-proof="authored" data-by="ai:claude">Modify:</span> <span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/tools/checkpoint.py`</span>

* <span data-proof="authored" data-by="ai:claude">Test:</span> <span data-proof="authored" data-by="ai:claude">`tests/test_capture.py`,</span> <span data-proof="authored" data-by="ai:claude">`tests/test_checkpoint.py`</span>

**<span data-proof="authored" data-by="ai:claude">Step 1: Write the failing tests</span>**

<span data-proof="authored" data-by="ai:claude">Append to</span> <span data-proof="authored" data-by="ai:claude">`tests/test_capture.py`:</span>

```python proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MTIxMCwiYXR0cnMiOnsiYnkiOiJhaTpjbGF1ZGUifX1d
def test_capture_returns_candidates_and_task_context(
    conn: sqlite3.Connection, seeded_actor: str
) -> None:
    # seed a prior idea and a prior checkpoint under the same task
    from ideahub_mcp.tools.checkpoint import CheckpointInput, checkpoint_idea
    prior = capture_idea(
        conn,
        CaptureInput(content="scorer ladder phase-1", scope="s1", actor=seeded_actor,
                     task_ref="t1"),
    )
    checkpoint_idea(
        conn,
        CheckpointInput(content="sibling observation", scope="s1", actor=seeded_actor,
                        task_ref="t1"),
    )

    out = capture_idea(
        conn,
        CaptureInput(
            content="scorer ladder final write",
            scope="s1",
            actor=seeded_actor,
            task_ref="t1",
        ),
    )
    # annotate_candidates include the prior idea but not the checkpoint
    ids = [c.id for c in out.annotate_candidates]
    assert prior.id in ids
    kinds = {c.kind for c in out.annotate_candidates}
    assert kinds.issubset({"idea"})
    # task_context carries the task_ref and some recent siblings
    assert out.task_context.task_ref == "t1"
    assert isinstance(out.task_context.recent_ids, list)
```

<span data-proof="authored" data-by="ai:claude">Append to</span> <span data-proof="authored" data-by="ai:claude">`tests/test_checkpoint.py`:</span>

```python proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6NjcyLCJhdHRycyI6eyJieSI6ImFpOmNsYXVkZSJ9fV0=
def test_checkpoint_returns_candidates_and_task_context(
    conn: sqlite3.Connection, seeded_actor: str
) -> None:
    from ideahub_mcp.tools.capture import CaptureInput, capture_idea
    prior = capture_idea(
        conn,
        CaptureInput(content="scorer ladder phase-1", scope="s1", actor=seeded_actor,
                     task_ref="t1"),
    )
    out = checkpoint_idea(
        conn,
        CheckpointInput(
            content="scorer ladder sibling",
            scope="s1",
            actor=seeded_actor,
            task_ref="t1",
        ),
    )
    assert prior.id in [c.id for c in out.annotate_candidates]
    assert out.task_context.task_ref == "t1"
```

**<span data-proof="authored" data-by="ai:claude">Step 2: Run the tests to verify they fail</span>**

<span data-proof="authored" data-by="ai:claude">Run:</span> <span data-proof="authored" data-by="ai:claude">`uv run pytest tests/test_capture.py::test_capture_returns_candidates_and_task_context tests/test_checkpoint.py::test_checkpoint_returns_candidates_and_task_context -v`
Expected: FAIL — outputs lack those fields.</span>

**<span data-proof="authored" data-by="ai:claude">Step 3: Extend outputs and wire the scorer</span>**

<span data-proof="authored" data-by="ai:claude">In</span> <span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/tools/capture.py`:</span>

1. <span data-proof="authored" data-by="ai:claude">Import:</span>

```python proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6ODIsImF0dHJzIjp7ImJ5IjoiYWk6Y2xhdWRlIn19XQ==
from ideahub_mcp.tools.candidates import CandidateItem, score_candidates_for_write
```

1. <span data-proof="authored" data-by="ai:claude">Add a</span> <span data-proof="authored" data-by="ai:claude">`TaskContext`</span> <span data-proof="authored" data-by="ai:claude">model at module scope:</span>

```python proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6ODAsImF0dHJzIjp7ImJ5IjoiYWk6Y2xhdWRlIn19XQ==
class TaskContext(BaseModel):
    task_ref: str | None
    recent_ids: list[str]
```

1. <span data-proof="authored" data-by="ai:claude">Extend</span> <span data-proof="authored" data-by="ai:claude">`CaptureOutput`:</span>

```python proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6NDgyLCJhdHRycyI6eyJieSI6ImFpOmNsYXVkZSJ9fV0=
class CaptureOutput(BaseModel):
    id: str
    scope: str
    actor: str
    originator: str | None
    created_at: str
    suggested_tags: list[str]
    actor_created: bool = False
    task_ref: str | None = None
    annotate_candidates: list[CandidateItem] = Field(default_factory=list)
    related_candidates: list[CandidateItem] = Field(default_factory=list)
    task_context: TaskContext = Field(
        default_factory=lambda: TaskContext(task_ref=None, recent_ids=[])
    )
```

1. <span data-proof="authored" data-by="ai:claude">Add a helper near the bottom of the file:</span>

```python proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6NDM4LCJhdHRycyI6eyJieSI6ImFpOmNsYXVkZSJ9fV0=
def _task_context(
    conn: sqlite3.Connection, task_ref: str | None, current_id: str
) -> TaskContext:
    if not task_ref:
        return TaskContext(task_ref=None, recent_ids=[])
    rows = conn.execute(
        "SELECT id FROM idea WHERE task_ref = ? AND id != ? "
        "ORDER BY created_at DESC LIMIT 10",
        (task_ref, current_id),
    ).fetchall()
    return TaskContext(task_ref=task_ref, recent_ids=[r[0] for r in rows])
```

1. <span data-proof="authored" data-by="ai:claude">In both return paths of</span> <span data-proof="authored" data-by="ai:claude">`capture_idea`, populate the new fields:</span>

```python proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6Mzc4LCJhdHRycyI6eyJieSI6ImFpOmNsYXVkZSJ9fV0=
cands = score_candidates_for_write(
    conn,
    content=input_.content,
    scope=input_.scope,
    originator=input_.originator,
    task_ref=input_.task_ref,
)
return CaptureOutput(
    # ...existing fields...
    annotate_candidates=cands.annotate_candidates,
    related_candidates=cands.related_candidates,
    task_context=_task_context(conn, input_.task_ref, new_id),
)
```

<span data-proof="authored" data-by="ai:claude">For the dedup path, use</span> <span data-proof="authored" data-by="ai:claude">`dup[0]`</span> <span data-proof="authored" data-by="ai:claude">as the current id.</span>

<span data-proof="authored" data-by="ai:claude">Do the equivalent wiring in</span> <span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/tools/checkpoint.py`:</span>

* <span data-proof="authored" data-by="ai:claude">Add</span> <span data-proof="authored" data-by="ai:claude">`TaskContext`</span> <span data-proof="authored" data-by="ai:claude">import/definition (reuse by importing from capture, or redefine; prefer importing:</span> <span data-proof="authored" data-by="ai:claude">`from ideahub_mcp.tools.capture import TaskContext`).</span>

* <span data-proof="authored" data-by="ai:claude">Extend</span> <span data-proof="authored" data-by="ai:claude">`CheckpointOutput`</span> <span data-proof="authored" data-by="ai:claude">with</span> <span data-proof="authored" data-by="ai:claude">`annotate_candidates`,</span> <span data-proof="authored" data-by="ai:claude">`related_candidates`,</span> <span data-proof="authored" data-by="ai:claude">`task_context`.</span>

* <span data-proof="authored" data-by="ai:claude">Populate from</span> <span data-proof="authored" data-by="ai:claude">`score_candidates_for_write`.</span>

**<span data-proof="authored" data-by="ai:claude">Step 4: Run tests to verify they pass</span>**

<span data-proof="authored" data-by="ai:claude">Run:</span> <span data-proof="authored" data-by="ai:claude">`uv run pytest tests/test_capture.py tests/test_checkpoint.py tests/test_candidates.py -v`
Expected: PASS.</span>

**<span data-proof="authored" data-by="ai:claude">Step 5: Commit</span>**

```bash proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MzkzLCJhdHRycyI6eyJieSI6ImFpOmNsYXVkZSJ9fV0=
git add src/ideahub_mcp/tools/capture.py src/ideahub_mcp/tools/checkpoint.py tests/test_capture.py tests/test_checkpoint.py
git commit -m "$(cat <<'EOF'
Return annotate_candidates, related_candidates, and task_context from capture and checkpoint so the write itself carries the signal needed for the next memory move

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

***

## <span data-proof="authored" data-by="ai:claude">Task 8: Default-exclude checkpoints from search, list, and dump</span>

**<span data-proof="authored" data-by="ai:claude">Files:</span>**

* <span data-proof="authored" data-by="ai:claude">Modify:</span> <span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/tools/search.py`</span>

* <span data-proof="authored" data-by="ai:claude">Modify:</span> <span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/tools/list_ideas.py`</span>

* <span data-proof="authored" data-by="ai:claude">Modify:</span> <span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/tools/dump.py`</span>

* <span data-proof="authored" data-by="ai:claude">Test:</span> <span data-proof="authored" data-by="ai:claude">`tests/test_search.py`,</span> <span data-proof="authored" data-by="ai:claude">`tests/test_list.py`,</span> <span data-proof="authored" data-by="ai:claude">`tests/test_dump.py`</span>

**<span data-proof="authored" data-by="ai:claude">Step 1: Write the failing tests</span>**

<span data-proof="authored" data-by="ai:claude">Append a test in each of the three test files that:</span>

* <span data-proof="authored" data-by="ai:claude">Seeds one</span> <span data-proof="authored" data-by="ai:claude">`idea`</span> <span data-proof="authored" data-by="ai:claude">row and one</span> <span data-proof="authored" data-by="ai:claude">`checkpoint`</span> <span data-proof="authored" data-by="ai:claude">row in the same scope with identical content terms.</span>

* <span data-proof="authored" data-by="ai:claude">Calls the tool with defaults and asserts only the</span> <span data-proof="authored" data-by="ai:claude">`idea`</span> <span data-proof="authored" data-by="ai:claude">is returned.</span>

* <span data-proof="authored" data-by="ai:claude">Calls the tool with</span> <span data-proof="authored" data-by="ai:claude">`include_checkpoints=True`</span> <span data-proof="authored" data-by="ai:claude">and asserts both are returned.</span>

<span data-proof="authored" data-by="ai:claude">Example for</span> <span data-proof="authored" data-by="ai:claude">`tests/test_search.py`</span> <span data-proof="authored" data-by="ai:claude">(adapt fixtures to existing patterns):</span>

```python proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6NzUzLCJhdHRycyI6eyJieSI6ImFpOmNsYXVkZSJ9fV0=
def test_search_default_excludes_checkpoints(conn: sqlite3.Connection, seeded_actor: str) -> None:
    conn.execute(
        "INSERT INTO idea (id, content, scope, actor_id, tags, created_at, kind) VALUES "
        "('i1','writeback phase','s1',?, '[]', datetime('now'), 'idea'),"
        "('c1','writeback phase','s1',?, '[]', datetime('now'), 'checkpoint')",
        (seeded_actor, seeded_actor),
    )
    out = search_ideas(conn, SearchInput(query="writeback", scope="s1"))
    ids = {h.id for h in out.hits}
    assert "i1" in ids
    assert "c1" not in ids

    out2 = search_ideas(
        conn, SearchInput(query="writeback", scope="s1", include_checkpoints=True)
    )
    ids2 = {h.id for h in out2.hits}
    assert {"i1", "c1"}.issubset(ids2)
```

**<span data-proof="authored" data-by="ai:claude">Step 2: Run the tests to verify they fail</span>**

<span data-proof="authored" data-by="ai:claude">Run:</span> <span data-proof="authored" data-by="ai:claude">`uv run pytest tests/test_search.py tests/test_list.py tests/test_dump.py -v -k checkpoint`
Expected: FAIL.</span>

**<span data-proof="authored" data-by="ai:claude">Step 3: Implement the filters</span>**

<span data-proof="authored" data-by="ai:claude">In each of the three input models (`SearchInput`,</span> <span data-proof="authored" data-by="ai:claude">`ListInput`,</span> <span data-proof="authored" data-by="ai:claude">`DumpInput`), add:</span>

```python proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MzMsImF0dHJzIjp7ImJ5IjoiYWk6Y2xhdWRlIn19XQ==
include_checkpoints: bool = False
```

<span data-proof="authored" data-by="ai:claude">In each query, add one line:</span>

```python proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MTY0LCJhdHRycyI6eyJieSI6ImFpOmNsYXVkZSJ9fV0=
if not input_.include_checkpoints:
    where.append("i.kind = 'idea'")   # search.py uses alias `i`
# or for list/dump (no alias):
    where.append("kind = 'idea'")
```

<span data-proof="authored" data-by="ai:claude">For</span> <span data-proof="authored" data-by="ai:claude">`search.py`, the FTS join already uses alias</span> <span data-proof="authored" data-by="ai:claude">`i`, so</span> <span data-proof="authored" data-by="ai:claude">`i.kind = 'idea'`</span> <span data-proof="authored" data-by="ai:claude">is the right form.</span>

**<span data-proof="authored" data-by="ai:claude">Step 4: Run tests to verify they pass</span>**

<span data-proof="authored" data-by="ai:claude">Run:</span> <span data-proof="authored" data-by="ai:claude">`uv run pytest tests/test_search.py tests/test_list.py tests/test_dump.py -v`
Expected: PASS.</span>

**<span data-proof="authored" data-by="ai:claude">Step 5: Commit</span>**

```bash proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6NDIyLCJhdHRycyI6eyJieSI6ImFpOmNsYXVkZSJ9fV0=
git add src/ideahub_mcp/tools/search.py src/ideahub_mcp/tools/list_ideas.py src/ideahub_mcp/tools/dump.py tests/test_search.py tests/test_list.py tests/test_dump.py
git commit -m "$(cat <<'EOF'
Default-exclude checkpoints from search, list, and dump so cheap working traces do not bleed into orientation surfaces; opt in with include_checkpoints

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

***

## <span data-proof="authored" data-by="ai:claude">Task 9: Server wiring — register checkpoint, thread task_ref, rewrite descriptions</span>

**<span data-proof="authored" data-by="ai:claude">Files:</span>**

* <span data-proof="authored" data-by="ai:claude">Modify:</span> <span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/server.py`</span>

**<span data-proof="authored" data-by="ai:claude">Step 1: Write the failing test</span>**

<span data-proof="authored" data-by="ai:claude">This task is exercised by the existing</span> <span data-proof="authored" data-by="ai:claude">`tests/test_server_smoke.py`</span> <span data-proof="authored" data-by="ai:claude">and</span> <span data-proof="authored" data-by="ai:claude">`tests/test_protocol_smoke.py`. Update the expected tool set first:</span>

<span data-proof="authored" data-by="ai:claude">In</span> <span data-proof="authored" data-by="ai:claude">`tests/test_server_smoke.py`, change</span> <span data-proof="authored" data-by="ai:claude">`EXPECTED_TOOLS`-equivalent assertion to include</span> <span data-proof="authored" data-by="ai:claude">`"checkpoint"`.</span>

<span data-proof="authored" data-by="ai:claude">In</span> <span data-proof="authored" data-by="ai:claude">`tests/test_protocol_smoke.py`, add</span> <span data-proof="authored" data-by="ai:claude">`"checkpoint"`</span> <span data-proof="authored" data-by="ai:claude">to</span> <span data-proof="authored" data-by="ai:claude">`EXPECTED_TOOLS`.</span>

**<span data-proof="authored" data-by="ai:claude">Step 2: Run to confirm they fail</span>**

<span data-proof="authored" data-by="ai:claude">Run:</span> <span data-proof="authored" data-by="ai:claude">`uv run pytest tests/test_server_smoke.py tests/test_protocol_smoke.py -v`
Expected: FAIL —</span> <span data-proof="authored" data-by="ai:claude">`checkpoint`</span> <span data-proof="authored" data-by="ai:claude">not registered.</span>

**<span data-proof="authored" data-by="ai:claude">Step 3: Wire the server</span>**

<span data-proof="authored" data-by="ai:claude">In</span> <span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/server.py`:</span>

1. <span data-proof="authored" data-by="ai:claude">Import:</span>

```python proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6NzMsImF0dHJzIjp7ImJ5IjoiYWk6Y2xhdWRlIn19XQ==
from ideahub_mcp.tools.checkpoint import CheckpointInput, checkpoint_idea
```

1. <span data-proof="authored" data-by="ai:claude">Register a</span> <span data-proof="authored" data-by="ai:claude">`checkpoint`</span> <span data-proof="authored" data-by="ai:claude">tool with this description:</span>

```python proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MTU0MSwiYXR0cnMiOnsiYnkiOiJhaTpjbGF1ZGUifX1d
@mcp.tool(
    description=(
        "Write a lightweight working-memory trace during a task. "
        "Use when: you form a non-trivial synthesis mid-task; you make a decision the "
        "session will depend on; you want a durable breadcrumb without promoting it to a "
        "full idea yet; you want to leave a visible trace of what changed in your "
        "understanding during the task. Do not use for final, standalone ideas that should "
        "survive the task — use `capture` for those. "
        "Optional `task_ref` groups all writes from the same task. Optional `kind_label` "
        "is a semantic hint (observation | decision | assumption | question | next_step). "
        "Returns scored `annotate_candidates` (existing ideas this trace may update) and "
        "`related_candidates` so the next memory move is obvious."
    )
)
def checkpoint(
    content: str,
    scope: str | None = None,
    tags: list[str] | None = None,
    originator: str | None = None,
    task_ref: str | None = None,
    kind_label: str | None = None,
    actor: str | None = None,
    ctx: Context | None = None,
) -> dict:
    c, aid, s, actor_created = _resolve(actor, scope, ctx)
    out = checkpoint_idea(
        c,
        CheckpointInput(
            content=content,
            scope=s,
            actor=aid,
            originator=originator,
            tags=tags or [],
            task_ref=task_ref,
            kind_label=kind_label,
            actor_created=actor_created,
        ),
    )
    return out.model_dump()
```

1. <span data-proof="authored" data-by="ai:claude">Add</span> <span data-proof="authored" data-by="ai:claude">`task_ref`</span> <span data-proof="authored" data-by="ai:claude">parameter to</span> <span data-proof="authored" data-by="ai:claude">`capture`,</span> <span data-proof="authored" data-by="ai:claude">`annotate`, and</span> <span data-proof="authored" data-by="ai:claude">`link`</span> <span data-proof="authored" data-by="ai:claude">tool wrappers. Thread it into each</span> <span data-proof="authored" data-by="ai:claude">`*Input(...)`.</span>
2. <span data-proof="authored" data-by="ai:claude">Rewrite the</span> <span data-proof="authored" data-by="ai:claude">`capture`</span> <span data-proof="authored" data-by="ai:claude">description:</span>

```
"Capture a new durable idea. "
"Use when: you reach a stable synthesis; you discover a reusable pattern; you want a "
"standalone idea that should survive task boundaries; a checkpoint has hardened into a "
"first-class concept. "
"If you only need a lightweight in-progress trace, use `checkpoint` instead. "
"`content` is required. `scope` and `actor` default from cwd and environment. "
"Optional `task_ref` groups all writes from the same task. "
"Returns `annotate_candidates` and `related_candidates` so the next memory move is obvious. "
"Idempotent within 5 seconds on identical content."
```

1. <span data-proof="authored" data-by="ai:claude">Rewrite the</span> <span data-proof="authored" data-by="ai:claude">`annotate`</span> <span data-proof="authored" data-by="ai:claude">description:</span>

```
"Append a note to an existing idea when current work confirms, sharpens, corrects, or "
"extends it. "
"Use when: the current task materially updates an existing idea; you want to attach new "
"evidence or a correction; you do not want to create a separate idea. "
"Optional `kind` labels the note semantically (confirmation, counterexample, observation, "
"follow-up, question, correction). Optional `task_ref` groups all writes from the same task."
```

1. <span data-proof="authored" data-by="ai:claude">Rewrite the</span> <span data-proof="authored" data-by="ai:claude">`link`</span> <span data-proof="authored" data-by="ai:claude">description:</span>

```
"Connect two ideas when current work reveals they are structurally related, evolved, "
"duplicated, or superseding one another. "
"`kind` ∈ {related, supersedes, evolved_from, duplicate}. `related` is canonicalized "
"(smaller id becomes source). Self-links rejected. Optional `task_ref` groups all writes "
"from the same task."
```

1. <span data-proof="authored" data-by="ai:claude">Add</span> <span data-proof="authored" data-by="ai:claude">`"checkpoint"`</span> <span data-proof="authored" data-by="ai:claude">to the</span> <span data-proof="authored" data-by="ai:claude">`tool_names`</span> <span data-proof="authored" data-by="ai:claude">tuple used by the</span> <span data-proof="authored" data-by="ai:claude">`ideahub://status`</span> <span data-proof="authored" data-by="ai:claude">resource.</span>

**<span data-proof="authored" data-by="ai:claude">Step 4: Run full suite</span>**

<span data-proof="authored" data-by="ai:claude">Run:</span> <span data-proof="authored" data-by="ai:claude">`uv run pytest -q && uv run ruff check . && uv run pyright`
Expected: all PASS.</span>

**<span data-proof="authored" data-by="ai:claude">Step 5: Commit</span>**

```bash proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MzczLCJhdHRycyI6eyJieSI6ImFpOmNsYXVkZSJ9fV0=
git add src/ideahub_mcp/server.py tests/test_server_smoke.py tests/test_protocol_smoke.py
git commit -m "$(cat <<'EOF'
Register the checkpoint tool, thread task_ref through every write-path tool, and rewrite descriptions normatively so a model reading the tool set cold can tell which verb to use

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

***

## <span data-proof="authored" data-by="ai:claude">Task 10: README update</span>

**<span data-proof="authored" data-by="ai:claude">Files:</span>**

* <span data-proof="authored" data-by="ai:claude">Modify:</span> <span data-proof="authored" data-by="ai:claude">`README.md`</span>

**<span data-proof="authored" data-by="ai:claude">Step 1: Update the tool table</span>**

<span data-proof="authored" data-by="ai:claude">Add a</span> <span data-proof="authored" data-by="ai:claude">`checkpoint`</span> <span data-proof="authored" data-by="ai:claude">row near</span> <span data-proof="authored" data-by="ai:claude">`capture`:</span>

| <span data-proof="authored" data-by="ai:claude">Tool</span>         | <span data-proof="authored" data-by="ai:claude">One-liner</span>                                                                               |
| ------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| <span data-proof="authored" data-by="ai:claude">`capture`</span>    | <span data-proof="authored" data-by="ai:claude">Durable idea. Use when work produces something worth preserving beyond the task.</span>        |
| <span data-proof="authored" data-by="ai:claude">`checkpoint`</span> | <span data-proof="authored" data-by="ai:claude">Lightweight working-memory trace. Use mid-task for observations, decisions, next steps.</span> |

<span data-proof="authored" data-by="ai:claude">Add a short "Writeback loop" paragraph under Discovery And Health or as its own section, explaining the two-tier write path and the</span> <span data-proof="authored" data-by="ai:claude">`task_ref`</span> <span data-proof="authored" data-by="ai:claude">convention. Keep it to ~8 lines. No new doc file.</span>

**<span data-proof="authored" data-by="ai:claude">Step 2: Commit</span>**

```bash proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MjUxLCJhdHRycyI6eyJieSI6ImFpOmNsYXVkZSJ9fV0=
git add README.md
git commit -m "$(cat <<'EOF'
Document the two-tier write path and the task_ref convention so readers coming in cold understand why there are two write verbs

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

***

## <span data-proof="authored" data-by="ai:claude">Task 11: Version bump, tag, release</span>

**<span data-proof="authored" data-by="ai:claude">Files:</span>**

* <span data-proof="authored" data-by="ai:claude">Modify:</span> <span data-proof="authored" data-by="ai:claude">`src/ideahub_mcp/__init__.py`</span>

* <span data-proof="authored" data-by="ai:claude">Modify:</span> <span data-proof="authored" data-by="ai:claude">`pyproject.toml`</span>

**<span data-proof="authored" data-by="ai:claude">Step 1: Bump version</span>**

```bash proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MTUzLCJhdHRycyI6eyJieSI6ImFpOmNsYXVkZSJ9fV0=
sed -i '' 's/__version__ = "0.1.2"/__version__ = "0.2.0"/' src/ideahub_mcp/__init__.py
sed -i '' 's/^version = "0.1.2"/version = "0.2.0"/' pyproject.toml
```

**<span data-proof="authored" data-by="ai:claude">Step 2: Full preflight</span>**

<span data-proof="authored" data-by="ai:claude">Run:</span>

```bash proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6NjUsImF0dHJzIjp7ImJ5IjoiYWk6Y2xhdWRlIn19XQ==
uv sync --dev
uv run ruff check .
uv run pyright
uv run pytest -q
```

<span data-proof="authored" data-by="ai:claude">Expected: all green.</span>

**<span data-proof="authored" data-by="ai:claude">Step 3: Commit, tag, push, release</span>**

```bash proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MTIyNywiYXR0cnMiOnsiYnkiOiJhaTpjbGF1ZGUifX1d
git add src/ideahub_mcp/__init__.py pyproject.toml
git commit -m "$(cat <<'EOF'
Bump to 0.2.0 for the writeback-loop release: checkpoint tool, uniform task_ref across write verbs, and candidate-surfacing returns

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git tag v0.2.0
git push origin main --tags
gh release create v0.2.0 --title "v0.2.0" --notes "$(cat <<'EOF'
Writeback Spec Phase 1.

- New `checkpoint` tool for cheap mid-task working-memory traces
- Uniform optional `task_ref` on all four write-path verbs (capture, checkpoint, annotate, link)
- `capture` and `checkpoint` now return scored `annotate_candidates`, `related_candidates`, and `task_context` — the write carries the signal for the next memory move
- Scoring ladder at write time: FTS/bm25 → shared task_ref → shared originator → recency
- Top-level search/list/dump default-exclude checkpoints; opt in with `include_checkpoints`
- Normative tool descriptions ("use when...") on all four write verbs

Out of scope (deliberate): `promote`, task lifecycle tools, kind-aware `related_ideas` scorer, memory-loop prompt, elicitation. These land in later phases once v0.2.0 data shows how the collapse paths actually behave.
EOF
)"
```

**<span data-proof="authored" data-by="ai:claude">Step 4: Reinstall locally</span>**

<span data-proof="authored" data-by="ai:claude">Once the PyPI publish workflow goes green:</span>

```bash proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6NzMsImF0dHJzIjp7ImJ5IjoiYWk6Y2xhdWRlIn19XQ==
uv tool upgrade ideahub-mcp
# or: uv tool install --reinstall ideahub-mcp
```

<span data-proof="authored" data-by="ai:claude">Then restart any MCP host holding the old process.</span>

***

## <span data-proof="authored" data-by="ai:claude">Post-Merge Verification</span>

<span data-proof="authored" data-by="ai:claude">After the release tag lands and PyPI publishes:</span>

1. <span data-proof="authored" data-by="ai:claude">In a scratch directory,</span> <span data-proof="authored" data-by="ai:claude">`uv tool run ideahub-mcp`</span> <span data-proof="authored" data-by="ai:claude">via an MCP client (Claude Code or Codex).</span>
2. <span data-proof="authored" data-by="ai:claude">Initialize. Confirm</span> <span data-proof="authored" data-by="ai:claude">`serverInfo.version == "0.2.0"`.</span>
3. <span data-proof="authored" data-by="ai:claude">Call</span> <span data-proof="authored" data-by="ai:claude">`list_tools`. Confirm</span> <span data-proof="authored" data-by="ai:claude">`checkpoint`</span> <span data-proof="authored" data-by="ai:claude">is present and the descriptions match the plan.</span>
4. <span data-proof="authored" data-by="ai:claude">Call</span> <span data-proof="authored" data-by="ai:claude">`checkpoint`</span> <span data-proof="authored" data-by="ai:claude">with a</span> <span data-proof="authored" data-by="ai:claude">`task_ref`. Confirm the response includes</span> <span data-proof="authored" data-by="ai:claude">`annotate_candidates`,</span> <span data-proof="authored" data-by="ai:claude">`related_candidates`, and</span> <span data-proof="authored" data-by="ai:claude">`task_context`.</span>
5. <span data-proof="authored" data-by="ai:claude">Read</span> <span data-proof="authored" data-by="ai:claude">`ideahub://status`. Confirm</span> <span data-proof="authored" data-by="ai:claude">`tools`</span> <span data-proof="authored" data-by="ai:claude">includes</span> <span data-proof="authored" data-by="ai:claude">`"checkpoint"`.</span>

<span data-proof="authored" data-by="ai:claude">If any of those fail, the release is a rollback candidate — bump to 0.2.1 with the fix rather than retagging 0.2.0.</span>

***

## <span data-proof="authored" data-by="ai:claude">What Success Looks Like</span>

<span data-proof="authored" data-by="ai:claude">The test is qualitative and observable in live use:</span>

* <span data-proof="authored" data-by="ai:claude">The model uses</span> <span data-proof="authored" data-by="ai:claude">`checkpoint`</span> <span data-proof="authored" data-by="ai:claude">during substantial work without being told.</span>

* <span data-proof="authored" data-by="ai:claude">Many checkpoints collapse into</span> <span data-proof="authored" data-by="ai:claude">`annotate`</span> <span data-proof="authored" data-by="ai:claude">calls because</span> <span data-proof="authored" data-by="ai:claude">`annotate_candidates`</span> <span data-proof="authored" data-by="ai:claude">surfaced the right target.</span>

* <span data-proof="authored" data-by="ai:claude">Durable</span> <span data-proof="authored" data-by="ai:claude">`capture`</span> <span data-proof="authored" data-by="ai:claude">calls become fewer and higher-signal.</span>

* <span data-proof="authored" data-by="ai:claude">`task_ref`</span> <span data-proof="authored" data-by="ai:claude">lets a human or model reconstruct a session's memory stream cleanly.</span>

<span data-proof="authored" data-by="ai:claude">If those behaviors do not emerge on first run, the next adjustment is candidate scoring — not the tool surface.</span>