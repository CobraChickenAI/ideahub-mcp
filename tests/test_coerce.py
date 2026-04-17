import pytest

from ideahub_mcp.util.coerce import coerce_str_list


def test_list_passthrough() -> None:
    assert coerce_str_list(["a", "b"]) == ["a", "b"]


def test_none_becomes_empty() -> None:
    assert coerce_str_list(None) == []


def test_json_encoded_list_is_parsed() -> None:
    assert coerce_str_list('["mcp", "claude-desktop"]') == ["mcp", "claude-desktop"]


def test_plain_string_becomes_single_tag() -> None:
    assert coerce_str_list("lonely") == ["lonely"]


def test_empty_string_becomes_empty() -> None:
    assert coerce_str_list("") == []


def test_non_list_json_raises() -> None:
    with pytest.raises(ValueError):
        coerce_str_list('{"a": 1}')
