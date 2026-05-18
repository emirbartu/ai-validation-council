"""Test divergence response parsing."""

import json

from council.debate.divergence import _extract_json, _parse_divergence_response


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


class TestParseDivergenceResponse:
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
        result = _parse_divergence_response(response)
        assert len(result) == 1
        assert result[0]["topic"] == "Market Size"

    def test_parses_no_divergences(self):
        response = json.dumps(
            {"no_divergences": True, "note": "All agents independently agreed"}
        )
        result = _parse_divergence_response(response)
        assert result == []

    def test_handles_invalid_json(self):
        result = _parse_divergence_response("not valid json at all")
        assert result == []

    def test_handles_empty_string(self):
        result = _parse_divergence_response("")
        assert result == []

    def test_handles_incomplete_json(self):
        response = '[{"topic": "x", "position_a"'
        result = _parse_divergence_response(response)
        assert result == []
