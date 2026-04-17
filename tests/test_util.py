import time

from ideahub_mcp.util.clock import utcnow_iso
from ideahub_mcp.util.ids import new_ulid


def test_new_ulid_is_sortable_by_creation_time() -> None:
    a = new_ulid()
    time.sleep(0.002)
    b = new_ulid()
    assert a < b
    assert len(a) == 26


def test_utcnow_iso_has_z_suffix() -> None:
    ts = utcnow_iso()
    assert ts.endswith("Z")
    assert "T" in ts
