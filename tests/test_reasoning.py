"""Offline checks for reasoning.py. Zero model calls — the real `claude` binary is never
invoked. Run: python tests/test_reasoning.py
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tcm import db
from tcm import reasoning as r

SAMPLE_DIGEST = (
    "[Provenance] Daily aggregates recorded by Apple Watch, exported 2026-08-14 06:12.\n"
    "Baseline window: 28 days ending 2026-08-13, 26 of 28 days present.\n"
    "[Yesterday vs this person's own baseline]\n"
    "- Resting heart rate 61 bpm - 8% above their 28-day median of 58 bpm; robust z +1.3.\n"
    "- Overnight HRV (SDNN) 38 ms - 21% below their 28-day median of 48 ms.\n"
)

REQUIRED_KEYS = {"reading_title", "tcm_pattern_summary", "plain_summary", "basis",
                  "confidence_note", "advice", "followup", "flags", "disclaimer"}


def test_stub_provider_valid_json_and_schema():
    raw = r.generate_reading(SAMPLE_DIGEST, "", {}, "sys", "knowledge", provider="stub")
    reading = json.loads(raw)  # must parse
    assert REQUIRED_KEYS.issubset(reading.keys())
    assert reading["disclaimer"] == db.DISCLAIMER


def test_stub_provider_basis_grounded_in_digest():
    raw = r.generate_reading(SAMPLE_DIGEST, "", {}, "sys", "knowledge", provider="stub")
    reading = json.loads(raw)
    digest_numbers = set(re.findall(r"\d+", SAMPLE_DIGEST))
    checked_text = " ".join(reading["basis"]) + " " + reading["plain_summary"]
    for n in re.findall(r"\d+", checked_text):
        assert n in digest_numbers, f"basis/plain_summary number {n!r} not in digest"


def test_stub_provider_no_numbers_when_digest_has_none():
    raw = r.generate_reading("no numeric content here", "", {}, "sys", "knowledge", provider="stub")
    reading = json.loads(raw)
    checked_text = " ".join(reading["basis"]) + " " + reading["plain_summary"]
    assert re.findall(r"\d+", checked_text) == []


def test_stub_provider_deterministic():
    raw1 = r.generate_reading(SAMPLE_DIGEST, "", {}, "sys", "knowledge", provider="stub")
    raw2 = r.generate_reading(SAMPLE_DIGEST, "", {}, "sys", "knowledge", provider="stub")
    assert raw1 == raw2


def test_unknown_provider_raises():
    try:
        r.generate_reading(SAMPLE_DIGEST, "", {}, "sys", "knowledge", provider="nope")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_build_user_text_contains_digest_verbatim():
    text = r.build_user_text(SAMPLE_DIGEST, "history stuff", {"age": 34})
    assert SAMPLE_DIGEST in text
    assert "history stuff" in text
    assert "34" in text


def test_build_user_text_omits_empty_history_and_profile():
    text = r.build_user_text(SAMPLE_DIGEST, "", {})
    assert text == SAMPLE_DIGEST


def test_build_command_shape():
    cmd = r.build_command("hi")
    assert isinstance(cmd, list)
    assert cmd[0] == "claude"
    assert "-p" in cmd
    assert "hi" in cmd
    assert "--json-schema" in cmd
    assert "--model" in cmd
    assert "claude-sonnet-5" in cmd
    assert "--append-system-prompt-file" in cmd
    assert "--output-format" in cmd


def test_build_command_disallowed_tools_disables_all():
    cmd = r.build_command("hi")
    assert "--disallowedTools" in cmd
    idx = cmd.index("--disallowedTools")
    disallowed = cmd[idx + 1]
    for tool in ("Bash", "Read", "Write", "Edit", "Glob", "Grep", "WebSearch", "WebFetch", "Agent"):
        assert tool in disallowed, f"{tool} missing from disallowedTools"


def test_prompt_hash_stable_and_sensitive():
    assert r.prompt_hash("x") == r.prompt_hash("x")
    assert r.prompt_hash("x") != r.prompt_hash("y")
    assert len(r.prompt_hash("x")) == 12


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(f"\n{len(fns)} reasoning tests passed")
