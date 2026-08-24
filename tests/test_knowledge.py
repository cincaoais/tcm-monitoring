"""M4 check: the knowledge file contains the five measurable pulses and NO texture-pulse character.

The strongest guardrail in the system is that the model is never SHOWN the texture vocabulary it
must not use. This test enforces that at the file level. Run: python tests/test_knowledge.py
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KNOWLEDGE = os.path.join(ROOT, "knowledge", "measurable_pulses.md")
NOTICE = os.path.join(ROOT, "knowledge", "NOTICE.md")

# Texture / depth / width / force / tension pulse-quality names. These must NEVER appear in the
# knowledge file. (跳动's 动 is a legitimate heartbeat verb and is not a texture quality, so it is
# deliberately not in this set.)
TEXTURE_CHARS = "浮沉弦紧滑涩细洪微弱大缓芤濡牢革"
MEASURABLE = ["数", "迟", "结", "代", "促"]


def test_no_texture_character():
    text = open(KNOWLEDGE, encoding="utf-8").read()
    hits = sorted({c for c in TEXTURE_CHARS if c in text})
    assert not hits, f"texture pulse character(s) leaked into knowledge file: {hits}"


def test_all_five_measurable_present():
    text = open(KNOWLEDGE, encoding="utf-8").read()
    missing = [p for p in MEASURABLE if p not in text]
    assert not missing, f"measurable pulse(s) missing from knowledge file: {missing}"


def test_no_herb_or_dosage():
    text = open(KNOWLEDGE, encoding="utf-8").read()
    for banned in ["方剂", "汤", "丸", "克", "钱"]:
        assert banned not in text, f"herb/dosage token {banned!r} leaked into knowledge file"


def test_notice_present_and_records_license_gap():
    assert os.path.exists(NOTICE), "knowledge/NOTICE.md must exist"
    n = open(NOTICE, encoding="utf-8").read()
    assert "LICENSE" in n and "ec03c594" in n and "促" in n


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(f"\n{len(fns)} knowledge tests passed")
