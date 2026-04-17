import sqlite3

import pytest

from ideahub_mcp.domain.actors import resolve_actor
from ideahub_mcp.errors import IdeaHubError
from ideahub_mcp.tools.recognize import RecognizeInput, recognize_actor


def test_list_all_actors(conn: sqlite3.Connection) -> None:
    resolve_actor(conn, explicit="human:m", client_info_name=None)
    resolve_actor(conn, explicit="agent:claude", client_info_name=None)
    out = recognize_actor(conn, RecognizeInput())
    ids = {a.id for a in out.actors}
    assert ids == {"human:m", "agent:claude"}


def test_single_actor_lookup(conn: sqlite3.Connection) -> None:
    resolve_actor(conn, explicit="human:m", client_info_name=None)
    out = recognize_actor(conn, RecognizeInput(id="human:m"))
    assert len(out.actors) == 1
    assert out.actors[0].kind == "human"


def test_unknown_actor_raises(conn: sqlite3.Connection) -> None:
    with pytest.raises(IdeaHubError) as exc:
        recognize_actor(conn, RecognizeInput(id="agent:ghost"))
    assert exc.value.code == "actor_not_found"
