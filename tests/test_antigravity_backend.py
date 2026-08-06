import json
from unittest.mock import MagicMock, patch

import antigravity_backend


def test_available_when_agy_exists():
    antigravity_backend._AGY_OK = None
    with patch("antigravity_backend.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert antigravity_backend.available() is True


def test_call_parses_agy_json_response(monkeypatch):
    antigravity_backend._AGY_OK = True
    monkeypatch.setattr(
        "antigravity_backend.get_settings",
        lambda: MagicMock(
            antigravity_model="gemini-3.5-flash-high",
            gemini_timeout=120,
        ),
    )
    stdout = json.dumps(
        {
            "status": "SUCCESS",
            "response": '[{"id":0,"skip":false,"summary":"Ok.","relevance":70}]',
        }
    )
    with patch("antigravity_backend.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=stdout, stderr="")
        out = antigravity_backend.call("Do JSON", "input", label="test")
    assert out == '[{"id":0,"skip":false,"summary":"Ok.","relevance":70}]'
    args = mock_run.call_args[0][0]
    assert args[0] == "agy"
    assert "--model=gemini-3.5-flash-high" in args
