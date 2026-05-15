# IdeaHub-MCP — Failure Mode Audit and Compound Resolutions

**Status:** Partially reconciled. Each pattern fixes the symptom AND installs a structural guard so the class of bug becomes self-detecting or self-preventing.

**Last reconciled:** 2026-05-02
**Repo state:** v0.4.0, four migrations applied (`001_init.sql`, `002_kind_and_task_ref.sql`, `003_checkpoint_kind_label.sql`, `004_content_hash.sql`).

**Shipped:** P1 (immediate fix only), P2 (immediate fix only), P3, P5, P6, P7 — all landed in v0.3.0. Tool annotations, helper dedup, and identifier normalization shipped in v0.4.0 (post-eval hygiene, not audit-driven).

**Open:** P1 structural guard (candidate utilization telemetry), P2 structural guard (task_ref alias surface + nearby_task_refs in writeback), P4 (orphan / staleness detection + corpus_health envelope).

The standard: a one-line patch that makes the immediate test pass is not a resolution. A resolution closes the door behind itself.

---

## P1 — Token overhead on the writeback loop

🟡 **Partially shipped v0.3.0** (commits `0339bdb` / `ae6fe81`) — `candidates` parameter promoted to the tool surface with `0` as opt-out. Structural guard (candidate_offer telemetry table + utilization-driven default tuning) **not shipped**.

### Diagnosis

Every `capture` and `checkpoint` invocation pays a fixed ~1,000-token tax for a candidate envelope the caller may not need on this turn. The cost is structural, not accidental:

| Where | What |
|---|---|
| `tools/candidates.py:96` | `max_candidates: int = 5` — hardcoded at the call site, not on the tool surface |
| `tools/capture.py:98-105`, `tools/capture.py:137-144` | `score_candidates_for_write` runs unconditionally on every write |
| `tools/checkpoint.py:105-112` | Same unconditional call on every checkpoint |
| Output shape | Up to 5 `annotate_candidates` + 5 `related_candidates`, each carrying `id`, `kind`, `preview` (120 chars), `score`, `why`, `reasons` (list), `created_at` |

The 20:1 response-to-input ratio is a load-bearing design choice — the writeback loop is what makes the surface model-facing rather than developer-facing — but it is paid even when the model has just decided "this is a fire-and-forget breadcrumb." Blast radius: silent token waste at every write, multiplied across the entire session graph. A 50-checkpoint session burns ~50,000 output tokens on candidates the model will not act on.

The fix is not to delete the loop. The fix is to let the model say "I don't need it" or "give me three" without the protocol changing under it.

### Immediate fix

Promote `max_candidates` from a function default to a tool parameter on `capture` and `checkpoint`. Allow `0` to mean "skip scoring entirely." Default stays at `5` so existing callers see no behavior change.

Concretely:

| File | Change |
|---|---|
| `server.py:121-129` (`capture` signature) | Add `candidates: int = 5` param, range `[0, 10]` |
| `server.py:160-171` (`checkpoint` signature) | Same |
| `tools/capture.py:14-21` (`CaptureInput`) | Add `candidates: int = Field(5, ge=0, le=10)` |
| `tools/checkpoint.py:16-26` (`CheckpointInput`) | Same |
| `tools/capture.py:86-157` (`capture_idea`) | If `input_.candidates == 0`, skip the `score_candidates_for_write` call and return empty lists for `annotate_candidates` / `related_candidates`. Otherwise pass `max_candidates=input_.candidates` through. |
| `tools/checkpoint.py:85-127` (`checkpoint_idea`) | Same |
| `tools/candidates.py:89-98` | No signature change required — already accepts `max_candidates`. |

Tool-description text on `capture` and `checkpoint` must spell out the contract so the model knows the lever exists: "`candidates` (default 5, max 10, 0 to skip) controls how many annotate/related suggestions are returned. Set to 0 when capturing a fire-and-forget trace; raise to 10 when actively triaging."

### Structural guard

A fix at the parameter level closes the immediate hole. The category — *unconfigurable response shape on a model-facing tool* — closes only when the system measures whether each candidate the model is paying for actually gets used.

Add a `candidate_use` table that records, per write, whether any of the returned candidate IDs subsequently appeared as the target of an `annotate` or `link` call within N minutes (configurable, default 30) under the same `task_ref`. A daily digest surfaces the *candidate utilization rate*. When utilization stays below ~10% for a tool×scope pair, the default `candidates` value for that pair is automatically lowered. The system tunes its own response shape from observed signal, not from intuition.

Migration sketch (`004_candidate_telemetry.sql`):

```sql
CREATE TABLE candidate_offer (
  write_id     TEXT NOT NULL REFERENCES idea(id) ON DELETE CASCADE,
  candidate_id TEXT NOT NULL,
  kind         TEXT NOT NULL CHECK (kind IN ('annotate','related')),
  position     INTEGER NOT NULL,
  offered_at   TEXT NOT NULL,
  consumed_at  TEXT,
  PRIMARY KEY (write_id, candidate_id, kind)
);
CREATE INDEX candidate_offer_consumed_idx
  ON candidate_offer (offered_at) WHERE consumed_at IS NULL;
```

`annotate` and `link` mark `consumed_at` when their `target` matches any open offer within the window. A new internal helper `_record_offers(conn, write_id, cands)` is called from `capture_idea` / `checkpoint_idea` after scoring.

### Test surface

| Test | Asserts |
|---|---|
| `test_capture.py::test_candidates_zero_returns_empty_lists` | `capture(content=..., candidates=0)` returns `annotate_candidates == [] and related_candidates == []` AND that `score_candidates_for_write` is not called (assert via fakeable hook or query count) |
| `test_capture.py::test_candidates_param_caps_response` | `capture(content=..., candidates=3)` returns `len(annotate_candidates) <= 3 and len(related_candidates) <= 3` |
| `test_capture.py::test_candidates_default_unchanged` | Existing callers with no `candidates` param still see the v0.2.1 shape (5 each) |
| `test_capture.py::test_candidates_out_of_range` | `candidates=11` raises `ValidationError` |
| `test_candidate_telemetry.py::test_offer_recorded_on_capture` | After `capture(candidates=5)`, `candidate_offer` has 5 annotate + 5 related rows for the new id |
| `test_candidate_telemetry.py::test_offer_consumed_by_annotate` | After `capture` then `annotate(target=offered_id)` within window, the offer row's `consumed_at` is set |

---

## P2 — `task_ref` sprawl

🟡 **Partially shipped v0.3.0** (commit `e856b6a`) — `normalize_task_ref` collapses the lexical sprawl at the input boundary. Structural guard (task_ref_alias table, `nearby_task_refs` field on the writeback envelope, `task_ref_alias_of` write parameter) **not shipped**.

### Diagnosis

`task_ref` is a free-form `TEXT` column (`002_kind_and_task_ref.sql:3`) with no normalization, no taxonomy, and no near-duplicate detection. The Pydantic validator on `CaptureInput.task_ref` (`tools/capture.py:28-33`) only coerces empty string to None. Two sessions working the same problem will produce `"writeback-phase-1"` and `"writeback_phase_1"` and `"writeback phase 1"` and the corpus is silently partitioned into three subgraphs that all look connected from inside themselves.

The blast radius is the worst kind: degraded relevance with no error. `_task_context` (`tools/capture.py:73-83`) returns `recent_ids` only for exact `task_ref` matches, so a model joining a task under a slightly different label sees an empty thread and concludes correctly that "this is a new task" — when it is not.

The discipline-on-the-model fix ("just be careful with task_refs") is the same anti-pattern as the FTS hyphen workaround: it offloads the structural failure onto the caller.

### Immediate fix

Two-step normalization at the input boundary, applied in one place (`util/coerce.py` is the natural home alongside `coerce_str_list`):

```python
_TASK_REF_RE = re.compile(r"[^a-z0-9]+")

def normalize_task_ref(v: object) -> str | None:
    if v is None or v == "":
        return None
    if not isinstance(v, str):
        raise TypeError("task_ref must be a string")
    s = _TASK_REF_RE.sub("-", v.strip().lower()).strip("-")
    return s or None
```

Wire it into the `field_validator` for `task_ref` on `CaptureInput`, `CheckpointInput`, `AnnotateInput`, `LinkInput`. Three of those four already have an empty-string-to-None validator that this replaces.

This collapses the trivial sprawl ("writeback phase 1" vs "writeback-phase-1") at the boundary, which is where you want to do it — never enter the corpus in two forms.

### Structural guard

Normalization handles the lexical case. The semantic case — `"writeback-phase-1"` vs `"writeback-spec-phase-1"` — needs detection, not normalization. The system cannot know two strings mean the same thing, but it can flag them.

Add a lightweight task-ref alias surface and surface near-duplicates back to the model in the writeback envelope:

| Component | Behavior |
|---|---|
| New table `task_ref_alias` | Maps `(canonical, alias)` pairs. Used by `_task_context` to widen `recent_ids` lookup beyond exact match. |
| New computed view `task_ref_index` | Distinct `task_ref` values, write count, first/last seen, sample content (latest preview). |
| New field on `CaptureOutput.task_context` | `nearby_task_refs: list[NearbyTaskRef]` — up to 3 distinct task_refs whose normalized form is within edit-distance 2 OR whose recent ideas FTS-match the current write's content above a threshold. Each entry carries `{task_ref, recent_id, why}` so the model can decide: *use that thread*, *alias it*, or *ignore*. |
| Tool surface | Existing tools gain optional `task_ref_alias_of: str` on writes, which writes a row in `task_ref_alias` and is then honored by `_task_context` and the daily digest. |

Sprawl becomes a thing the model is *told about* on the next write, not a thing that requires human archaeology to discover.

Migration sketch (`005_task_ref_aliases.sql`):

```sql
CREATE TABLE task_ref_alias (
  canonical  TEXT NOT NULL,
  alias      TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (canonical, alias)
);
CREATE INDEX task_ref_alias_canonical_idx ON task_ref_alias (canonical);
CREATE INDEX task_ref_alias_alias_idx     ON task_ref_alias (alias);
```

### Test surface

| Test | Asserts |
|---|---|
| `test_coerce.py::test_normalize_task_ref_collapses_separators` | `normalize_task_ref("Writeback Phase 1")` == `"writeback-phase-1"` |
| `test_coerce.py::test_normalize_task_ref_idempotent` | `normalize_task_ref(normalize_task_ref(x)) == normalize_task_ref(x)` for arbitrary x (hypothesis) |
| `test_capture.py::test_task_ref_normalized_at_write` | `capture(task_ref="Foo Bar")` stores `"foo-bar"`, returns `"foo-bar"` |
| `test_capture.py::test_nearby_task_refs_surfaced` | After two captures with `task_ref="writeback-phase-1"` and `"writeback-phase-2"`, a third capture under `"writeback-phase-1"` returns `nearby_task_refs` containing the phase-2 thread |
| `test_capture.py::test_task_ref_alias_widens_context` | After `capture(task_ref="x", task_ref_alias_of="y")`, a subsequent `capture(task_ref="y")` finds the x-tagged write in `recent_ids` |

---

## P3 — FTS5 hyphen-as-syntax collision

✅ **Shipped v0.3.0** (commit `a4e151a`) — `util/fts.py` chokepoint with `sanitize_fts_query` and `raw_fts_query`; auto/raw mode on the `search` tool. The lint guard from the structural-guard section was tried and **subsequently removed** (commit `55498f6`) as pseudo-safety any caller could route around by re-importing; the chokepoint is enforced by architecture, not by a grep.

### Diagnosis

`search_ideas` (`tools/search.py:32-69`) passes the user `query` directly to `idea_fts MATCH ?`. FTS5 reads `foo-bar` as the `foo` column minus the `bar` token (column-prefix syntax) and silently returns wrong-shaped results. No error is raised because FTS5 considers the query syntactically valid — it is just answering a different question than the model asked.

Other operators have the same shape: `:`, `^`, `*` at unexpected positions, leading `-`, unbalanced quotes. The hyphen is only the most common because the corpus is full of kebab-case identifiers (`task_ref` like `writeback-phase-1`, ULIDs, scope strings, branch names).

The current workaround — instruct the model to use spaces — is a discipline contract that any cold-read model violates.

The candidate scorer already solves the same problem one layer down. `_fts_query` in `tools/candidates.py:32-51` extracts alphanumeric tokens with a regex and quotes them defensively. `search_ideas` does not.

### Immediate fix

Two-mode behavior on `search`:

1. **Default mode (`query_mode="auto"`):** route the user query through a sanitizer that mirrors the candidate scorer's discipline — extract `[A-Za-z0-9_]+` tokens, quote each, join with `OR`. Hyphens become token separators. Quotes, colons, asterisks become inert. This is the right behavior 95% of the time and matches what the model expects from a "search" verb.
2. **Raw mode (`query_mode="raw"`):** pass through unchanged for callers who *do* want FTS5 syntax (advanced operators, phrase searches, NEAR). Raw mode wraps any FTS5 syntax error in `IdeaHubError` so the failure becomes loud.

Refactor: lift `_fts_query` and `_FTS_TOKEN_RE` from `tools/candidates.py` to a new `util/fts.py` and import from both call sites. Add the `query_mode: Literal["auto", "raw"] = "auto"` parameter to `SearchInput` and the `search` tool surface. Preserve the existing test corpus.

Concretely in `tools/search.py:32-37`:

```python
from ideahub_mcp.util.fts import sanitize_fts_query

def search_ideas(conn, input_):
    if input_.query_mode == "auto":
        match_query = sanitize_fts_query(input_.query)
        if not match_query:
            return SearchOutput(hits=[], count=0, query=input_.query)
    else:
        match_query = input_.query
    where = ["idea_fts MATCH ?"]
    params = [match_query]
    ...
```

Tool description must surface the mode: "`query` is sanitized by default — hyphens, colons, and other FTS5 operators are treated as content. Use `query_mode='raw'` for phrase queries, NEAR, or column-qualified syntax."

### Structural guard

The category here is *callers passing untrusted text into FTS5 without sanitization*. There is exactly one other call site in the codebase right now (`candidates.py`) and it already sanitizes — but a new tool added six months from now will not, unless the only path to FTS5 is through one helper.

Two-part guard:

1. **One-way path:** `util/fts.py` exposes two functions only — `sanitize_fts_query(text: str) -> str` and `raw_fts_query(text: str) -> str`. The latter validates by attempting an `EXPLAIN QUERY PLAN` parse against a throwaway in-memory FTS5 table and raises `IdeaHubError` on syntax failure. **No tool may construct an FTS5 MATCH parameter by any other path.**
2. **Lint guard:** add a ruff/grep CI check that fails the build if the substring `idea_fts MATCH` appears in any `.py` file outside `util/fts.py`. The pattern becomes architecturally singular instead of remembered convention.

A snippet for `pyproject.toml` or a new `tests/test_lint.py`:

```python
def test_only_fts_helper_uses_match():
    offenders = []
    for p in Path("src/ideahub_mcp").rglob("*.py"):
        if p.name == "fts.py":
            continue
        if "idea_fts MATCH" in p.read_text():
            offenders.append(str(p))
    assert offenders == [], f"Bypassing util/fts.py: {offenders}"
```

### Test surface

| Test | Asserts |
|---|---|
| `test_search.py::test_hyphenated_query_finds_kebab_content` | `search(query="writeback-phase-1")` finds an idea whose content contains `writeback-phase-1` |
| `test_search.py::test_special_chars_inert_in_auto_mode` | Queries with `:`, `*`, `^`, leading `-`, unbalanced `"` do not raise and return reasonable hits |
| `test_search.py::test_raw_mode_passthrough` | `search(query='"foo bar"', query_mode="raw")` performs a phrase search |
| `test_search.py::test_raw_mode_syntax_error_loud` | `search(query="foo:::", query_mode="raw")` raises `IdeaHubError`, not silent empty result |
| `test_lint.py::test_only_fts_helper_uses_match` | (above) |
| `test_property.py::test_sanitize_idempotent` | hypothesis: `sanitize_fts_query(sanitize_fts_query(x)) == sanitize_fts_query(x)` |

---

## P4 — No orphan or staleness detection

🔴 **Not shipped.** No `orphans` or `stale` tool exists; the writeback envelope carries no `corpus_health` field. Open work.

### Diagnosis

An idea captured and never linked, annotated, or referenced becomes a dead node. The graph has no surface that says "these N ideas are aging without connections." `dump`, `list`, and `search` all rank by recency or relevance — they actively *hide* the orphan problem because dead ideas drop out of the recent window. The corpus accumulates rot silently.

Blast radius: degraded retrieval over time. The longer the corpus runs, the higher the orphan ratio, the lower the signal density of `dump` and `related`. There is no metric that surfaces this — until a human notices "huh, why are my dumps full of stuff I forgot about."

### Immediate fix

Add an `orphans` tool that returns ideas matching all of:

- `kind = 'idea'` (checkpoints are expected to be transient)
- `archived_at IS NULL`
- No inbound or outbound row in `idea_link`
- No row in `idea_note` (other than possibly the auto-archive note, which won't exist for non-archived rows)
- `created_at` older than a threshold (default 14 days, configurable)

Plus a separate `stale` tool: ideas with no *recent* note or link activity over a window (default 30 days), regardless of historical activity. An idea that was active in March but silent since is "stale," not "orphan."

Both return the same shape as `list`, with an additional `last_activity_at` column.

### Structural guard

A tool the model can call is necessary but not sufficient — the model has to *remember* to call it. The compound move is to plumb staleness back into the writeback envelope itself:

When `capture` or `checkpoint` runs and the corpus contains stale or orphan ideas in the same scope, the response includes a small `corpus_health` envelope:

| Field | Meaning |
|---|---|
| `orphan_count` | Ideas in scope with no links/notes older than threshold |
| `stale_count` | Ideas in scope with no recent activity over window |
| `attention_sample` | Up to 3 idea ids the model should consider linking, annotating, or archiving |

This is bounded (3 ids, ~200 tokens) and elidable via the same `candidates=0` mechanism from P1. The graph self-surfaces its own decay on the writeback path that already exists, without adding a new tool the model has to remember.

A daily-digest scheduled task (via the `schedule` skill) writes a `kind='digest'` checkpoint summarizing health metrics, so the corpus has its own pulse trace.

Migration: none required — both detections are queries over existing tables.

### Test surface

| Test | Asserts |
|---|---|
| `test_orphans.py::test_orphan_idea_surfaced` | An idea with no notes/links, older than 14 days, appears in `orphans()` output |
| `test_orphans.py::test_linked_idea_not_orphan` | Same idea, after `link(...)`, no longer appears |
| `test_orphans.py::test_archived_excluded` | Archived idea never appears in `orphans()` regardless of age |
| `test_capture.py::test_corpus_health_in_writeback` | After seeding stale ideas, a fresh `capture` returns `corpus_health.stale_count > 0` and `attention_sample` populated |
| `test_capture.py::test_corpus_health_elided_when_candidates_zero` | `capture(candidates=0)` returns no `corpus_health` envelope (P1 contract holds) |

---

## P5 — Cowork MCP host stringifies list-typed params

✅ **Shipped v0.3.0** (commit `97fe87b`) — `StrList` annotated type in `util/types.py` bakes the coercion into the type system. Lint guard `test_lint.py::test_no_bare_list_str_in_inputs` enforces that no tool input model declares a bare `list[str]`.

### Diagnosis

The Cowork MCP host serializes list-typed parameters as JSON strings before they reach Pydantic validation. The current workaround lives in `util/coerce.py:coerce_str_list` and is wired into `tags` validators on `CaptureInput`, `CheckpointInput`, etc. It works but it is host-specific and silent.

The fragility: a new list-typed parameter added to a new tool will arrive stringified and fail validation with a confusing error, because the developer adding the tool will not remember to wire `coerce_str_list` into a `field_validator(mode="before")`. Discovery happens by user pain, not by the type system.

### Immediate fix

Already present: `coerce_str_list` is correct. Audit the existing input models to confirm every `list[str]` field has the `mode="before"` coercer. Quick grep target:

| Model | List fields | Has coercer? |
|---|---|---|
| `CaptureInput` | `tags` | yes |
| `CheckpointInput` | `tags` | yes |
| `ListInput` | `tags_any`, `tags_all` | check |
| `RelatedInput` | (none) | n/a |
| `LinkInput` | (none) | n/a |

Fix any gap discovered during the audit.

### Structural guard

The category — *list-typed parameters silently fail when host stringifies them* — closes when the type system enforces the coercer:

Define a `StrList` type alias once and use it everywhere instead of `list[str]`:

```python
# util/types.py
from typing import Annotated
from pydantic import BeforeValidator
from ideahub_mcp.util.coerce import coerce_str_list

StrList = Annotated[list[str], BeforeValidator(coerce_str_list)]
```

Replace every `list[str] = Field(default_factory=list)` annotation with `StrList = Field(default_factory=list)`. The coercion is now a property of the type, not a property of the validator the developer remembered to write. Grep guard analogous to P3:

```python
def test_no_bare_list_str_in_inputs():
    offenders = []
    for p in Path("src/ideahub_mcp/tools").rglob("*.py"):
        text = p.read_text()
        if "list[str]" in text and "StrList" not in text:
            offenders.append(str(p))
    assert offenders == []
```

### Test surface

| Test | Asserts |
|---|---|
| `test_coerce.py::test_strlist_accepts_json_string` | A model with `tags: StrList` accepts `tags='["a","b"]'` and produces `["a","b"]` |
| `test_coerce.py::test_strlist_accepts_native_list` | Same model accepts `tags=["a","b"]` |
| `test_coerce.py::test_strlist_rejects_garbage` | `tags="not-json"` raises `ValidationError` cleanly |
| `test_lint.py::test_no_bare_list_str_in_inputs` | (above) |

---

## P6 — Shallow deduplication

✅ **Shipped v0.3.0** (migration `22b691f` adds `004_content_hash.sql`, capture rewrite in `0339bdb`) — content_hash column with partial index, hash-based dedup widened beyond the 5-second window, `dup_attempt` notes record collisions for provenance. The `possible_duplicates` writeback field from the structural guard was not adopted; the existing `annotate_candidates` envelope was deemed sufficient.

### Diagnosis

The 5-second idempotency window in `capture_idea` (`tools/capture.py:87-93`) catches accidental double-fires of *byte-identical content from the same actor in the same scope*. It catches nothing else:

| Duplicate type | Caught? |
|---|---|
| Byte-identical content, same actor, same scope, within 5s | yes |
| Byte-identical content, different actor | no |
| Byte-identical content, > 5s later | no |
| Content with trailing whitespace difference | no |
| Content rephrased ("X is broken" vs "X has a bug") | no — out of scope, embeddings would be needed |

The middle three cases are the real failure surface. A model that re-captures the same observation under a slightly different framing 10 minutes later (because it does not realize it already wrote that idea) creates a structural duplicate that breaks the "single source of truth" invariant.

OB1's pattern (SHA-256 content fingerprinting with metadata merging on collision) is a known better baseline.

### Immediate fix

Add a `content_hash` column to `idea` (SHA-256 over normalized content — strip leading/trailing whitespace, collapse internal whitespace runs to single spaces). Index it. On `capture_idea`, look up by `(scope, content_hash)` first; if a hit exists, treat as the dedup branch (return the existing id, merge tags into the existing row, append a `kind='dup_attempt'` note recording the second actor and timestamp).

This widens dedup from "5-second same-actor exact byte match" to "any-time same-scope normalized match," which catches the second and third rows in the table above. The fourth row (whitespace difference) is handled by the normalization in the hash computation. The fifth (rephrase) is explicitly out of scope per the constraint that this is not an embeddings product.

Migration sketch (`006_content_hash.sql`):

```sql
ALTER TABLE idea ADD COLUMN content_hash TEXT;
UPDATE idea SET content_hash = -- backfill in Python migration step
  ...;
CREATE INDEX idea_scope_hash_idx ON idea (scope, content_hash) WHERE archived_at IS NULL;
```

The 5-second exact-match check stays as a fast path before hash computation — it is cheaper and handles the accidental double-fire case without a hash round-trip.

### Structural guard

Hash-based dedup catches lexical duplicates. The category — *the corpus contains semantically-redundant ideas the system cannot detect* — needs a different surface.

Two-part guard:

1. **Merge-on-collision is logged:** every dedup hit writes a `kind='dup_attempt'` note on the canonical idea, with the would-be actor, timestamp, and tag delta. The note stream becomes a record of "how often does this idea get re-derived?" — a strong signal that the idea is load-bearing AND a forensic trail when an actor expected to write something new and instead got the dedup branch.
2. **Near-dup surfacing on write:** the existing `score_candidates_for_write` ladder already returns `lexical_match` candidates. Promote any candidate above an FTS bm25 threshold (top hit, score within X of perfect) into a dedicated `possible_duplicates` field on the writeback envelope, separate from `related_candidates`. The model sees: "we already have an idea 92% lexically similar to this one — link, supersede, or proceed." Token cost is bounded: zero in the common case, ~100 tokens when fired.

### Test surface

| Test | Asserts |
|---|---|
| `test_capture.py::test_dedup_byte_identical_across_actors` | Two captures of identical content from different actors return the same id; the second writes a `dup_attempt` note |
| `test_capture.py::test_dedup_whitespace_normalized` | `"hello world"` and `"hello  world"` (two spaces) collide |
| `test_capture.py::test_dedup_outside_idempotency_window` | Two captures of identical content > 5s apart still collide via hash |
| `test_capture.py::test_dedup_does_not_cross_scope` | Same content under different scopes does not collide |
| `test_capture.py::test_possible_duplicates_surfaced` | Write nearly-identical (FTS-similar but not hash-equal) content; `possible_duplicates` is non-empty |
| `test_migrations.py::test_006_backfills_content_hash` | After migration, every existing row has a non-null `content_hash` matching the recomputed value |

---

## P7 — No checkpoint-to-idea promotion

✅ **Shipped v0.3.0** (commit `8b1d11a`) — `promote` tool mutates `kind` from `checkpoint` to `idea` while preserving the id; writes a `kind='promotion'` note recording the original `kind_label`. Reverse demotion explicitly not implemented. The `promotion_suggestion` writeback field from the structural guard was not adopted.

### Diagnosis

Checkpoints and ideas live in the same table (`idea.kind in ('idea','checkpoint')`) and share the ID namespace, but there is no `promote` verb. When a checkpoint turns out to be load-bearing, the workaround is to call `capture` with the same content — which produces a *new* idea with a new ID and no structural link to the checkpoint that spawned it. The provenance chain is broken at the most important seam: the moment a transient observation hardens into a durable concept.

Blast radius: every promotion is silent fragmentation. The graph cannot answer "where did this idea come from" for any idea that started life as a checkpoint, because the link does not exist.

### Immediate fix

Add a `promote` tool that takes a `checkpoint_id`, mutates the row's `kind` from `'checkpoint'` to `'idea'`, and writes an `idea_note` of `kind='promotion'` recording the original `kind_label`, the actor, and the timestamp. The ID is preserved — every existing link, annotation, and reference continues to work.

Tool surface:

```python
@mcp.tool(description=(
    "Promote a checkpoint to a durable idea. "
    "Use when a working-memory trace turns out to be load-bearing — the synthesis "
    "has hardened, the decision is stable, the observation is reusable. "
    "Preserves the id; the checkpoint's history (links, annotations, task_ref) "
    "carries forward. Writes a `kind='promotion'` note for provenance."
))
def promote(
    id: str,
    actor: str | None = None,
    originator: str | None = None,
    ctx: Context | None = None,
) -> dict: ...
```

Implementation:

```python
def promote_checkpoint(conn, input_):
    row = conn.execute(
        "SELECT kind, kind_label FROM idea WHERE id = ?",
        (input_.id,),
    ).fetchone()
    if row is None:
        raise IdeaHubError(f"no idea with id {input_.id}")
    if row[0] != "checkpoint":
        raise IdeaHubError(f"idea {input_.id} is already kind={row[0]}")
    conn.execute(
        "UPDATE idea SET kind = 'idea' WHERE id = ?", (input_.id,),
    )
    note_id = new_ulid()
    conn.execute(
        "INSERT INTO idea_note (id, idea_id, kind, content, actor_id, originator_id, created_at) "
        "VALUES (?, ?, 'promotion', ?, ?, ?, ?)",
        (note_id, input_.id, f"promoted from checkpoint (was kind_label={row[1]})",
         input_.actor, input_.originator, utcnow_iso()),
    )
    return get_idea(conn, GetInput(id=input_.id))
```

### Structural guard

The category — *transient state hardening into durable state without leaving a trail* — closes when the system actively suggests promotion at the moments it is most likely warranted.

Two surfaces:

1. **Auto-suggestion in writeback:** when `capture` runs and the new idea has high lexical similarity to one or more existing checkpoints (FTS bm25 top hit, threshold tuned), the response includes a `promotion_suggestion` field: "Checkpoint X already says nearly the same thing — promote it instead of creating a duplicate idea." This connects P6 (dedup) and P7 (promotion) on the writeback path: the system catches the rephrase-as-promotion case before the duplicate is written.
2. **Reverse demotion explicitly disallowed:** an idea cannot become a checkpoint. Once promoted, the row stays an idea. This is enforced by the `promote_checkpoint` precondition (`if row[0] != "checkpoint"`) and by NOT adding a `demote` verb. Promotion is one-way; the YARN-level analogue is that history is append-only, and TML's invariant of fail-closed structural change applies here.

### Test surface

| Test | Asserts |
|---|---|
| `test_promote.py::test_promote_changes_kind` | After `promote(id=cid)`, `get(id=cid).kind == "idea"` |
| `test_promote.py::test_promote_preserves_id_and_links` | A link created against the checkpoint id resolves identically after promotion |
| `test_promote.py::test_promote_writes_note` | After promotion, `get(id=cid).notes` includes a `kind='promotion'` note |
| `test_promote.py::test_promote_idempotent_via_loud_error` | `promote(id=cid)` twice — second call raises `IdeaHubError`, does not silently no-op |
| `test_promote.py::test_no_demote_verb_exists` | Server tool list does not contain `demote` |
| `test_capture.py::test_promotion_suggested_on_near_duplicate_idea_capture` | Capturing content lexically near a checkpoint surfaces the checkpoint id as `promotion_suggestion` |

---

## Cross-cutting observations

| Observation | Implication |
|---|---|
| Writeback envelope is the steering wheel | Every structural guard above (P1 candidate-utilization, P2 nearby task_refs, P4 corpus_health, P6 possible_duplicates, P7 promotion_suggestion) ships back through the same response surface. The model-facing writeback loop is not just an output — it is the system's primary interface for telling the model *what it should consider doing next*. Treat it as a designed surface, not a side effect. |
| Discipline-on-the-model is a smell | The hyphen workaround, the task_ref free-form contract, and the future-developer reliance on remembering to wire `coerce_str_list` are all instances of "the model/developer is expected to know." Each compound resolution above pushes that contract into the type system, the storage layer, or a singular helper module. |
| Telemetry without a feedback loop is decoration | The candidate_offer table (P1) and the dup_attempt notes (P6) are only valuable if the daily digest reads them and the system tunes its own defaults from the result. Build the read path at the same time as the write path, or do not bother. |
| Migration cadence | This audit implies up to four migrations (`004_candidate_telemetry`, `005_task_ref_aliases`, `006_content_hash`, plus any minor for `promote` if it touches schema — it does not). Sequence them in order of payoff: P3 first (no migration, biggest UX win), P1 next (one migration, biggest token win), P6 third (one migration, biggest correctness win). P2, P4, P7 follow. |

## Sequencing

### Predicted vs. actual

The original sequencing predicted a four-release cadence. Actual delivery collapsed five patterns into v0.3.0 (P1 immediate fix, P2 immediate fix, P3, P5, P6, P7) by treating the audit's "immediate fix" sections as one cohesive landing rather than per-pattern releases. The structural guards — the telemetry, alias, and corpus-health surfaces — are the open work.

| Phase | Patterns | Migrations | Status |
|---|---|---|---|
| v0.3.0 | P1 (param), P2 (normalize), P3, P5, P6, P7 | `004_content_hash.sql` | ✅ Shipped |
| v0.4.0 | Tool annotations, helper dedup, identifier normalization, eval suite (post-eval hygiene, not audit-driven) | none | ✅ Shipped |
| _open_ | P1 structural guard (candidate utilization telemetry) | `004_candidate_telemetry.sql` (sketched) | 🔴 Not shipped |
| _open_ | P2 structural guard (task_ref alias surface + `nearby_task_refs` writeback) | `005_task_ref_aliases.sql` (sketched) | 🔴 Not shipped |
| _open_ | P4 (orphan / staleness detection + `corpus_health` envelope) | none required | 🔴 Not shipped |
