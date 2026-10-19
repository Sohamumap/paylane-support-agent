"""Validate eval inputs before paying for a live run."""

import json

import pytest

from evals import runner


def test_loading_all_conversations_validates_their_regexes():
    assert len(runner.load_conversations()) == 12
    assert len(runner.load_conversations(extra=True)) >= 2


def test_backspace_from_a_json_regex_is_rejected(tmp_path, monkeypatch):
    spec = {"id": "broken", "expect": {"forbidden": ["\brefund\b"]}}
    (tmp_path / "broken.json").write_text(json.dumps(spec))
    monkeypatch.setattr(runner, "CONVERSATIONS", tmp_path)
    with pytest.raises(ValueError, match="control character in regex"):
        runner.load_conversations()


def test_loading_followup_patterns_does_not_add_them_to_forbidden_replies():
    spec = next(spec for spec in runner.load_conversations() if spec["id"] == "c11")
    assert "\\bbalance\\b" not in spec["expect"].get("forbidden", [])


def test_a_run_saves_the_inputs_that_its_score_describes(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "TRANSCRIPTS", tmp_path)
    spec = {"id": "c99", "title": "Manifest fixture", "category": "unit", "expect": {}, "turns": []}
    fake_record = {"id": "c99", "title": spec["title"], "category": "unit", "model": "fake",
                   "effort": "low", "turns": [], "final": {"tickets": []}, "checks": [], "passed": True}
    monkeypatch.setattr(runner, "run_conversation", lambda *args, **kwargs: fake_record.copy())
    folder, _, _ = runner.run_suite([spec], client=object(), model="fake", effort="low", workers=1)
    manifest = json.loads((folder / "manifest.json").read_text())
    assert manifest["started_at_utc"].endswith("+00:00")
    assert manifest["completed_at_utc"].endswith("+00:00")
    assert manifest["model_requested"] == "fake"
    assert len(manifest["source_sha256"]["paylane/rulebook.md"]) == 64
    assert len(manifest["conversations_sha256"]["c99"]) == 64
