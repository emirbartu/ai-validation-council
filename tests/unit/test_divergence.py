"""Test divergence response parsing.

Covers both the new status-envelope contract and a legacy list-returning
parser preserved for back-compat with existing consumers.
"""

import json

from council.debate.divergence import (
    _extract_json,
    _parse_divergence_response,
    parse_divergence_response_legacy,
)


class TestExtractJson:
    def test_extracts_array(self):
        text = 'Some text before [{"topic": "x"}] and after'
        result = _extract_json(text)
        assert result == '[{"topic": "x"}]'

    def test_extracts_object(self):
        text = '{"no_divergences": true, "note": "agents agreed"}'
        result = _extract_json(text)
        assert result == text

    def test_no_json_returns_none(self):
        result = _extract_json("plain text without json")
        assert result is None

    def test_nested_brackets(self):
        text = '{"data": [1, 2, 3], "more": true} extra'
        result = _extract_json(text)
        assert result is not None
        assert isinstance(json.loads(result), (dict, list))


class TestParseDivergenceResponseEnvelope:
    """New contract: ``_parse_divergence_response`` always returns an envelope."""

    def test_parses_valid_divergence_array(self):
        response = json.dumps(
            [
                {
                    "topic": "Market Size",
                    "position_a": {"agent": "market_analyst", "claim": "TAM is $12B"},
                    "position_b": {"agent": "devils_advocate", "claim": "TAM is under $2B"},
                    "resolution_test": "Check Grand View Research 2026 dental software report",
                }
            ]
        )
        envelope = _parse_divergence_response(response)
        assert envelope["status"] == "parsed"
        assert len(envelope["divergences"]) == 1
        assert envelope["divergences"][0]["topic"] == "Market Size"

    def test_parses_no_divergences(self):
        response = json.dumps({"no_divergences": True, "note": "All agents independently agreed"})
        envelope = _parse_divergence_response(response)
        assert envelope["status"] == "empty"
        assert envelope["divergences"] == []

    def test_invalid_json_is_parse_error_not_silent(self):
        envelope = _parse_divergence_response("not valid json at all")
        assert envelope["status"] == "parse_error"
        assert envelope["divergences"] == []
        assert envelope["error"]
        assert envelope["raw"] == "not valid json at all"

    def test_empty_string_is_parse_error(self):
        envelope = _parse_divergence_response("")
        assert envelope["status"] == "parse_error"
        assert envelope["divergences"] == []

    def test_incomplete_json_is_parse_error(self):
        envelope = _parse_divergence_response('[{"topic": "x", "position_a"')
        assert envelope["status"] == "parse_error"
        assert envelope["divergences"] == []

    def test_unexpected_shape_is_parse_error(self):
        envelope = _parse_divergence_response(json.dumps({"weird_key": 123}))
        assert envelope["status"] == "parse_error"


class TestLegacyParser:
    """Legacy parser: returns ``[]`` on parse error (back-compat shim)."""

    def test_parses_valid_divergence_array_legacy(self):
        response = json.dumps(
            [
                {
                    "topic": "Market Size",
                    "position_a": {"agent": "market_analyst", "claim": "TAM is $12B"},
                    "position_b": {"agent": "devils_advocate", "claim": "TAM is under $2B"},
                    "resolution_test": "Check Grand View Research 2026 dental software report",
                }
            ]
        )
        result = parse_divergence_response_legacy(response)
        assert len(result) == 1
        assert result[0]["topic"] == "Market Size"

    def test_parses_no_divergences_legacy(self):
        response = json.dumps({"no_divergences": True, "note": "All agents independently agreed"})
        result = parse_divergence_response_legacy(response)
        assert result == []

    def test_handles_invalid_json_legacy(self):
        result = parse_divergence_response_legacy("not valid json at all")
        assert result == []

    def test_handles_empty_string_legacy(self):
        result = parse_divergence_response_legacy("")
        assert result == []

    def test_handles_incomplete_json_legacy(self):
        response = '[{"topic": "x", "position_a"'
        result = parse_divergence_response_legacy(response)
        assert result == []
