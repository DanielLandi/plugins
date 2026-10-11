import os
import re
import unicodedata
import warnings

import pytest

from conftest import REPO

MV = REPO / "music-video"
TERMS_FILE = REPO / ".private-terms.txt"
# The repo owner's public attribution, as in the other plugins.
ATTRIBUTION = {MV / ".claude-plugin/plugin.json", MV / "LICENSE"}
SKIP_DIRS = {"node_modules", ".venv", "__pycache__", ".pytest_cache"}
# The marketplace's public address (install lines, homepage) is the repo owner's handle, not private data.
PUBLIC = re.compile(r"github\.com/DanielLandi/plugins|DanielLandi/plugins|@daniellandi\b|marketplace (?:add|update) \w+")
GENERIC = [
    (re.compile(r"/Users/|/home/[a-z]|[A-Za-z]:\\\\Users\\\\|/private/tmp"), "an absolute home path"),
    (re.compile(r"[\w.+-]+@(?!example\.(?:com|org)\b)[A-Za-z][\w-]*(?:\.[\w-]+)*\.[A-Za-z]{2,}\b"), "an email address"),
    (re.compile(r"\b(?:sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|xox[bp]-[A-Za-z0-9-]{10,})"), "a token"),
]


def _files():
    for f in sorted(MV.rglob("*")):
        if f.is_file() and not SKIP_DIRS & set(f.relative_to(MV).parts):
            yield f
    # The plugin's tests are public too, this scanner included.
    tests = REPO / "tests"
    yield from sorted([*tests.glob("test_mv_*.py"), tests / "mv_fixtures.py"])


def _terms():
    if not TERMS_FILE.is_file():
        if os.environ.get("MV_PUBLISH"):
            pytest.fail(f"{TERMS_FILE.name} is missing: the publish check needs the denylist")
        warnings.warn(f"{TERMS_FILE.name} missing: the denylist scan is skipped (generic checks still run)")
        return []
    return _patterns(TERMS_FILE.read_text(encoding="utf-8").splitlines())


def _plain(text):
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def _patterns(lines):
    """Each term as written, without accents, and (for several words) as a slug: `a-b`, `a_b`, `ab`."""
    forms = set()
    for term in (t.strip() for t in lines):
        if not term:
            continue
        forms |= {term, _plain(term)}
        words = re.findall(r"[a-z0-9]+", _plain(term).lower())
        if len(words) > 1:
            forms |= {"-".join(words), "_".join(words), "".join(words)}
    # One trie-shaped pattern (hundreds of terms over megabytes): each position costs the trie's depth, not the
    # number of terms. Matching is on lower-cased text.
    return [re.compile(rf"(?<![a-z])(?:{_trie({f.lower() for f in forms})})(?![a-z])", re.I)] if forms else []


def _trie(words):
    root = {}
    for w in words:
        node = root
        for ch in w:
            node = node.setdefault(ch, {})
        node[""] = {}

    def pattern(node):
        ends = "" in node
        branches = [re.escape(ch) + pattern(child) for ch, child in sorted(node.items()) if ch]
        if not branches:
            return ""
        body = branches[0] if len(branches) == 1 else "(?:" + "|".join(branches) + ")"
        return f"(?:{body})?" if ends else body

    return pattern(root)


def _text(f):
    data = f.read_bytes()
    try:
        return data.decode("utf-8"), True
    except UnicodeDecodeError:
        # A binary (a model, an image): only its readable strings can carry a name.
        return "\n".join(m.decode("latin-1") for m in re.findall(rb"[\x20-\x7e\xc0-\xff]{4,}", data)), False


def _hits(files, terms):
    hits = []
    for f in files:
        if f in ATTRIBUTION:
            continue
        text = PUBLIC.sub("", _text(f)[0])
        name = f.relative_to(REPO) if f.is_relative_to(REPO) else f
        hits += [f"{name}: {m.group(0)}" for t in terms for m in [t.search(text)] if m]
    return hits


def test_no_private_terms():
    assert _hits(_files(), _terms()) == []


def test_tests_are_scanned_too():
    names = {f.name for f in _files()}
    assert {"mv_fixtures.py", "test_mv_workspace.py", "test_mv_privacy.py"} <= names


def test_no_paths_emails_or_tokens():
    hits = []
    for f in _files():
        if f.name == "test_mv_privacy.py":
            continue  # it spells out the patterns it looks for; the denylist scan still covers it
        text, is_text = _text(f)
        if not is_text:
            continue
        for pattern, what in GENERIC:
            if f in ATTRIBUTION and what == "an email address":
                continue
            if m := pattern.search(text):
                hits.append(f"{f.relative_to(REPO)}: {what} ({m.group(0)[:40]})")
    assert hits == []


def test_scan_catches_a_planted_term(tmp_path):
    if not TERMS_FILE.is_file():
        pytest.skip("needs the local denylist")
    term = next(t.strip() for t in TERMS_FILE.read_text(encoding="utf-8").splitlines() if t.strip())
    planted = tmp_path / "planted.md"  # never inside the plugin: an interrupted run must not leave it there
    planted.write_text(f"a line with {term} in it\n", encoding="utf-8")
    assert _hits([planted], _terms())


def test_email_pattern_skips_versioned_file_names():
    email = next(p for p, what in GENERIC if what == "an email address")
    assert email.search("write to someone@mailhost.com today")
    assert not email.search("match-cut-anchor@1.0.0.mp4") and not email.search("pkg@4.0.534")


def test_terms_match_slug_and_unaccented_forms():
    pats = _patterns(["Night Owl Song", "Ônibus"])
    for text in ("the Night Owl Song", "night-owl-song.yaml", "night_owl_song", "nightowlsong", "onibus lotado"):
        assert any(p.search(text) for p in pats), text
    assert not any(p.search("a nightly owl") for p in pats)
