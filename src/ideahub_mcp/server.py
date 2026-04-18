from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Literal

from fastmcp import Context, FastMCP

from ideahub_mcp import __version__
from ideahub_mcp.domain.actors import resolve_actor
from ideahub_mcp.domain.scopes import resolve_scope
from ideahub_mcp.errors import IdeaHubError
from ideahub_mcp.observability.logging import configure_logging, get_logger
from ideahub_mcp.storage.backup import snapshot_store
from ideahub_mcp.storage.connection import open_connection
from ideahub_mcp.storage.migrations import apply_pending_migrations
from ideahub_mcp.tools.annotate import AnnotateInput, annotate_idea
from ideahub_mcp.tools.archive import ArchiveInput, archive_idea
from ideahub_mcp.tools.capture import CaptureInput, capture_idea
from ideahub_mcp.tools.checkpoint import CheckpointInput, checkpoint_idea
from ideahub_mcp.tools.dump import DumpInput, dump_ideas
from ideahub_mcp.tools.get import GetInput, get_idea
from ideahub_mcp.tools.link import LinkInput, link_ideas
from ideahub_mcp.tools.list_ideas import ListInput, list_ideas
from ideahub_mcp.tools.recognize import RecognizeInput, recognize_actor
from ideahub_mcp.tools.related import RelatedInput, related_ideas
from ideahub_mcp.tools.search import SearchInput, search_ideas

MIGRATIONS_DIR = Path(__file__).resolve().parent / "storage" / "migrations"


def home() -> Path:
    return Path(os.getenv("IDEAHUB_MCP_HOME") or Path.home() / ".ideahub-mcp").expanduser()


def _open_live(store: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(store, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def build_server() -> FastMCP:
    h = home()
    configure_logging(h / "logs")
    log = get_logger("server")

    store = h / "store.db"
    existed = store.exists()
    with open_connection(store) as conn:
        apply_pending_migrations(conn, MIGRATIONS_DIR)
    if existed:
        snapshot_store(store, h / "backups")

    mcp = FastMCP("ideahub-mcp", version=__version__)

    tool_names = (
        "capture", "checkpoint", "dump", "search", "list", "get",
        "related", "annotate", "archive", "link", "recognize", "ping",
    )

    @mcp.resource("ideahub://status")
    def status_resource() -> dict:
        return {
            "name": "ideahub-mcp",
            "version": __version__,
            "store": str(store),
            "home": str(h),
            "tools": [*tool_names],
        }

    @mcp.tool(
        description=(
            "Cheap health probe. Returns server name, package version, and store path. "
            "Use to confirm the ideahub-mcp server is connected and responsive."
        )
    )
    def ping() -> dict:
        return {
            "ok": True,
            "name": "ideahub-mcp",
            "version": __version__,
            "store": str(store),
        }

    def _client_info_name(ctx: Context | None) -> str | None:
        if ctx is None:
            return None
        try:
            return ctx.session.client_params.clientInfo.name  # type: ignore[attr-defined]
        except Exception:
            return None

    def _resolve(
        actor: str | None, scope: str | None, ctx: Context | None = None
    ) -> tuple[sqlite3.Connection, str, str, bool]:
        c = _open_live(store)
        sr = resolve_scope(explicit=scope, cwd=Path.cwd())
        if sr.fallback_to_global:
            log.info("scope_fallback_to_global", cwd=str(Path.cwd()))
        ar = resolve_actor(
            c, explicit=actor, client_info_name=_client_info_name(ctx)
        )
        return c, ar.id, sr.scope, ar.created

    @mcp.tool(
        description=(
            "Capture a new durable idea. "
            "Use when: you reach a stable synthesis; you discover a reusable pattern; "
            "you want a standalone idea that should survive task boundaries; a checkpoint "
            "has hardened into a first-class concept. "
            "If you only need a lightweight in-progress trace, use `checkpoint` instead. "
            "`content` is required. `scope` and `actor` default from cwd and environment. "
            "Optional `task_ref` groups all writes from the same task. "
            "Returns `annotate_candidates` and `related_candidates` so the next memory "
            "move is obvious. "
            "Idempotent within 5 seconds on identical content."
        )
    )
    def capture(
        content: str,
        scope: str | None = None,
        tags: list[str] | None = None,
        originator: str | None = None,
        task_ref: str | None = None,
        actor: str | None = None,
        ctx: Context | None = None,
    ) -> dict:
        c, aid, s, actor_created = _resolve(actor, scope, ctx)
        out = capture_idea(
            c,
            CaptureInput(
                content=content,
                scope=s,
                actor=aid,
                originator=originator,
                tags=tags or [],
                task_ref=task_ref,
                actor_created=actor_created,
            ),
        )
        return out.model_dump()

    @mcp.tool(
        description=(
            "Write a lightweight working-memory trace during a task. "
            "Use when: you form a non-trivial synthesis mid-task; you make a decision the "
            "session will depend on; you want a durable breadcrumb without promoting it "
            "to a full idea yet; you want to leave a visible trace of what changed in "
            "your understanding during the task. Do not use for final, standalone ideas "
            "that should survive the task — use `capture` for those. "
            "Optional `task_ref` groups all writes from the same task. Optional "
            "`kind_label` is a semantic hint (observation | decision | assumption | "
            "question | next_step). "
            "Returns scored `annotate_candidates` (existing ideas this trace may update) "
            "and `related_candidates` so the next memory move is obvious."
        )
    )
    def checkpoint(
        content: str,
        scope: str | None = None,
        tags: list[str] | None = None,
        originator: str | None = None,
        task_ref: str | None = None,
        kind_label: Literal["observation", "decision", "assumption", "question", "next_step"] | None = None,
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

    @mcp.tool(
        description=(
            "Dump the scoped corpus as a single text blob under a token budget. "
            "Use for orientation — 'what does this repo/user think about?'. "
            "Newest ideas first, latest note inlined by default, archived excluded by default. "
            "By default excludes kind='checkpoint' rows; pass "
            "include_checkpoints=True to include them."
        )
    )
    def dump(
        scope: str | None = None,
        since: str | None = None,
        actor: str | None = None,
        originator: str | None = None,
        limit_tokens: int = 50_000,
        include_all_notes: bool = False,
        include_archived: bool = False,
        include_checkpoints: bool = False,
        ctx: Context | None = None,
    ) -> dict:
        c, _aid, s, _ = _resolve(None, scope, ctx)
        out = dump_ideas(
            c,
            DumpInput(
                scope=s,
                since=since,
                actor=actor,
                originator=originator,
                limit_tokens=limit_tokens,
                include_all_notes=include_all_notes,
                include_archived=include_archived,
                include_checkpoints=include_checkpoints,
            ),
        )
        return out.model_dump()

    @mcp.tool(
        description=(
            "Full-text search ideas with FTS5 + bm25 ranking. Returns snippet, score, and id. "
            "Scope-optional; archived excluded by default. "
            "By default excludes kind='checkpoint' rows; pass "
            "include_checkpoints=True to include them."
        )
    )
    def search(
        query: str,
        scope: str | None = None,
        since: str | None = None,
        limit: int = 25,
        include_archived: bool = False,
        include_checkpoints: bool = False,
    ) -> dict:
        c = _open_live(store)
        out = search_ideas(
            c,
            SearchInput(
                query=query,
                scope=scope,
                since=since,
                limit=limit,
                include_archived=include_archived,
                include_checkpoints=include_checkpoints,
            ),
        )
        return out.model_dump()

    @mcp.tool(
        description=(
            "List ideas with filters (scope, actor, originator, tags_any, tags_all, since, until). "
            "Returns id, scope, actor, preview (120 chars), and created_at. "
            "Archived excluded by default. "
            "By default excludes kind='checkpoint' rows; pass "
            "include_checkpoints=True to include them."
        )
    )
    def list(  # noqa: A001
        scope: str | None = None,
        actor: str | None = None,
        originator: str | None = None,
        tags_any: list[str] | None = None,
        tags_all: list[str] | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 50,
        include_archived: bool = False,
        include_checkpoints: bool = False,
    ) -> dict:
        c = _open_live(store)
        out = list_ideas(
            c,
            ListInput(
                scope=scope,
                actor=actor,
                originator=originator,
                tags_any=tags_any or [],
                tags_all=tags_all or [],
                since=since,
                until=until,
                limit=limit,
                include_archived=include_archived,
                include_checkpoints=include_checkpoints,
            ),
        )
        return out.model_dump()

    @mcp.tool(description="Get a single idea by id with its notes and outbound links.")
    def get(id: str) -> dict:  # noqa: A002
        c = _open_live(store)
        return get_idea(c, GetInput(id=id)).model_dump()

    @mcp.tool(
        description=(
            "Find ideas related to the given id. Scoring: (1) tag overlap DESC, "
            "(2) shared originator (True first), (3) recency DESC. "
            "Within source scope unless cross_scope=True; archived excluded by default. "
            "By default excludes kind='checkpoint' rows; pass "
            "include_checkpoints=True to include them."
        )
    )
    def related(
        id: str,  # noqa: A002
        max: int = 10,  # noqa: A002
        cross_scope: bool = False,
        include_archived: bool = False,
        include_checkpoints: bool = False,
    ) -> dict:
        c = _open_live(store)
        return related_ideas(
            c,
            RelatedInput(
                id=id,
                max=max,
                cross_scope=cross_scope,
                include_archived=include_archived,
                include_checkpoints=include_checkpoints,
            ),
        ).model_dump()

    @mcp.tool(
        description=(
            "Append a note to an existing idea when current work confirms, sharpens, "
            "corrects, or extends it. "
            "Use when: the current task materially updates an existing idea; you want "
            "to attach new evidence or a correction; you do not want to create a "
            "separate idea. "
            "Optional `kind` labels the note semantically (confirmation, counterexample, "
            "observation, follow-up, question, correction). Optional `task_ref` groups "
            "all writes from the same task."
        )
    )
    def annotate(
        id: str,  # noqa: A002
        content: str,
        kind: str | None = None,
        actor: str | None = None,
        originator: str | None = None,
        task_ref: str | None = None,
        ctx: Context | None = None,
    ) -> dict:
        c, aid, _, _ = _resolve(actor, None, ctx)
        return annotate_idea(
            c,
            AnnotateInput(
                id=id,
                content=content,
                kind=kind,
                actor=aid,
                originator=originator,
                task_ref=task_ref,
            ),
        ).model_dump()

    @mcp.tool(
        description=(
            "Archive an idea (sets archived_at, writes kind='archive' note with reason). "
            "Idempotent. Archived ideas are excluded by default from list/search/dump."
        )
    )
    def archive(
        id: str,  # noqa: A002
        reason: str,
        actor: str | None = None,
        originator: str | None = None,
        ctx: Context | None = None,
    ) -> dict:
        c, aid, _, _ = _resolve(actor, None, ctx)
        return archive_idea(
            c, ArchiveInput(id=id, reason=reason, actor=aid, originator=originator)
        ).model_dump()

    @mcp.tool(
        description=(
            "Connect two ideas when current work reveals they are structurally related, "
            "evolved, duplicated, or superseding one another. "
            "`kind` ∈ {related, supersedes, evolved_from, duplicate}. `related` is "
            "canonicalized (smaller id becomes source). Self-links rejected. Optional "
            "`task_ref` groups all writes from the same task."
        )
    )
    def link(
        source_id: str,
        target_id: str,
        kind: str,
        task_ref: str | None = None,
    ) -> dict:
        c = _open_live(store)
        return link_ideas(
            c,
            LinkInput(
                source_id=source_id,
                target_id=target_id,
                kind=kind,
                task_ref=task_ref,
            ),
        ).model_dump()

    @mcp.tool(
        description=(
            "Inspect the actor table. Pass id for detail on one actor; omit to list all."
        )
    )
    def recognize(id: str | None = None) -> dict:  # noqa: A002
        c = _open_live(store)
        return recognize_actor(c, RecognizeInput(id=id)).model_dump()

    # Silence unused-import lint on imports that exist only for type surfaces.
    _ = IdeaHubError

    return mcp
