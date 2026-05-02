import json
from pathlib import Path

from ideahub_mcp.observability.logging import configure_logging, get_logger


def test_log_line_is_json(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    configure_logging(log_dir)
    log = get_logger("test")
    log.info("scope_fallback_to_global", actor="human:m", cwd="/tmp")
    log_file = log_dir / "ideahub_mcp.log"
    line = log_file.read_text().strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["event"] == "scope_fallback_to_global"
    assert payload["actor"] == "human:m"
