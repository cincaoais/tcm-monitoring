"""LLM reasoning adapter. A function + a provider string, not a class hierarchy.

`generate_reading(...)` returns the RAW model response text (a JSON string). It never
interprets that text — `validator.py` does that. Providers are dispatched by string so
adding one later is one function plus one dict entry, nothing upstream needs to change.

stdlib only: subprocess, json, time, hashlib, re, tempfile.
"""
import hashlib
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

from tcm import db

_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SYSTEM_PROMPT_FILE = str(_ROOT / "prompts" / "system_v1.md")
DEFAULT_SCHEMA_FILE = str(_ROOT / "schema" / "reading.json")
DEFAULT_MODEL = "claude-sonnet-5"
DISALLOWED_TOOLS = "Bash,Read,Write,Edit,Glob,Grep,WebSearch,WebFetch,Agent"

# ponytail: fixed backoff schedule (0s, 2s, 4s before attempts 1/2/3) — bump if the
# rolling rate-limit window turns out to need a longer tail.
RETRY_DELAYS = (0, 2, 4)


class ReasoningError(Exception):
    """Raised when the claude CLI fails on every attempt. Caller must not record a visit."""


def build_user_text(digest, history_digest, profile):
    """digest, then history_digest (if non-empty), then a short profile line.

    `digest` appears UNMODIFIED (verbatim substring) in the result.
    """
    parts = [digest]
    if history_digest:
        parts.append(history_digest)
    if profile:
        parts.append("[Profile] " + ", ".join(f"{k}: {v}" for k, v in profile.items()))
    return "\n\n".join(parts)


def build_command(user_text, *, system_prompt_file=DEFAULT_SYSTEM_PROMPT_FILE,
                   schema_file=DEFAULT_SCHEMA_FILE, model=DEFAULT_MODEL):
    """Build the argv list for the headless `claude` CLI call.

    `--json-schema` takes the schema JSON *inline*, not a path — so if `schema_file` is a real
    file, its (compacted, validated) content is embedded. `--disallowedTools` is placed LAST so its
    variadic `<tools...>` can't swallow a following flag.
    """
    schema_arg = schema_file
    p = Path(schema_file)
    if p.is_file():
        schema = json.loads(p.read_text(encoding="utf-8"))
        # The CLI's structured-output validator can't resolve external meta-schema refs; drop them.
        schema.pop("$schema", None)
        schema.pop("$id", None)
        schema_arg = json.dumps(schema)
    return [
        "claude", "-p", user_text,
        "--append-system-prompt-file", system_prompt_file,
        "--output-format", "json",
        "--json-schema", schema_arg,
        "--model", model,
        "--disallowedTools", DISALLOWED_TOOLS,
    ]


def prompt_hash(system_prompt):
    """sha256 hex, first 12 chars — stamps each visit with the prompt version."""
    return hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()[:12]


def _extract_structured_output(stdout):
    """Parse the `--output-format json` envelope; prefer structured_output, fall back to result."""
    envelope = json.loads(stdout)
    structured = envelope.get("structured_output")
    if structured is not None:
        return json.dumps(structured, ensure_ascii=False)
    return envelope.get("result", stdout)


def _generate_claude_code(digest, history_digest, profile, system_prompt, knowledge):
    """Shell out to the `claude` CLI in headless mode. Subscription/OAuth login only —
    no Agent SDK, no ANTHROPIC_API_KEY path.
    """
    user_text = build_user_text(digest, history_digest, profile)
    composed_system = system_prompt + "\n\n" + knowledge
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(composed_system)
        system_prompt_path = f.name
    try:
        cmd = build_command(user_text, system_prompt_file=system_prompt_path)
        last_err = None
        for delay in RETRY_DELAYS:
            if delay:
                time.sleep(delay)
            # encoding must be explicit: claude emits UTF-8 (Chinese), but text=True defaults to the
            # Windows locale (cp1252) and would crash decoding the response.
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    encoding="utf-8", errors="replace")
            if result.returncode == 0:
                return _extract_structured_output(result.stdout)
            # A non-zero exit is an expected outcome (rate limits), not a crash — retry.
            last_err = result.stderr.strip() or result.stdout.strip()
        raise ReasoningError(
            f"claude CLI failed after {len(RETRY_DELAYS)} attempts: {last_err}")
    finally:
        Path(system_prompt_path).unlink(missing_ok=True)


def _generate_stub(digest, history_digest, profile, system_prompt, knowledge):
    """Fixed, deterministic, valid reading JSON — zero model calls, for offline tests.

    basis/plain_summary reference only numbers pulled from `digest` itself (first 1-2
    found), so the validator's basis-grounding check passes for free. plain_summary has
    no TCM vocabulary — it's the "same claim in plain words" honesty check.
    """
    nums = re.findall(r"\d+", digest)[:2]
    if nums:
        basis = [f"digest reports the value {n}" for n in nums]
        plain_summary = ("Recent daily figures include " + " and ".join(nums) +
                          ", compared with your own recent history.")
    else:
        basis = ["digest contains no extractable numeric values for this reading"]
        plain_summary = "No numeric values were available for comparison in this reading."
    reading = {
        "reading_title": "Trend Check",
        "tcm_pattern_summary": "整体偏平和倾向",
        "plain_summary": plain_summary,
        "basis": basis,
        "confidence_note": ("Based only on daily rate/rhythm/HRV-family aggregates vs your "
                             "own baseline; no pulse, tongue, or lab data."),
        "advice": {
            "diet": ["规律三餐", "温热饮食为主"],
            "routine": ["固定起床时间"],
            "rest": ["午间小憩十分钟"],
            "exercise": ["饭后散步"],
        },
        "followup": {"what_to_watch": ["静息心率"], "recheck_in_days": 7},
        "flags": [],
        "disclaimer": db.DISCLAIMER,
    }
    return json.dumps(reading, ensure_ascii=False)


_PROVIDERS = {
    "stub": _generate_stub,
    "claude_code": _generate_claude_code,
}


def generate_reading(digest, history_digest, profile, system_prompt, knowledge,
                      provider="claude_code"):
    """Return the RAW model response text (a JSON string). Never interpret it — validator.py does."""
    try:
        fn = _PROVIDERS[provider]
    except KeyError:
        raise ValueError(f"unknown reasoning provider: {provider!r}") from None
    return fn(digest, history_digest, profile, system_prompt, knowledge)
