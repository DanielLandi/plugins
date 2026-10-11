import json
import re
import tomllib

from conftest import REPO

MV = REPO / "music-video"


def _inline(script):
    block = re.search(r"# /// script\n(.*?)# ///", script.read_text(encoding="utf-8"), re.S).group(1)
    return tomllib.loads("\n".join(l[2:] if l.startswith("# ") else "" for l in block.splitlines()))


def test_versions_agree():
    import musicvideo
    plugin = json.loads((MV / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
    market = json.loads((REPO / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    entry = next(p for p in market["plugins"] if p["name"] == "music-video")
    assert plugin["name"] == "music-video"
    assert plugin["version"] == entry["version"] == musicvideo.__version__ == "0.1.0"
    assert entry["source"] == "./music-video"


def test_inline_deps_are_in_root_pyproject():
    toml = _inline(MV / "scripts/music-video.py")
    project = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert set(toml["dependencies"]) <= set(project["dependencies"])
    assert toml["requires-python"] == project["requires-python"]


def test_help_runs(capsys):
    from musicvideo import cli
    try:
        cli.main(["--help"])
    except SystemExit as e:
        assert e.code == 0
    assert "music-video" in capsys.readouterr().out


def test_error_is_one_line(capsys):
    from musicvideo import cli
    from musicvideo.errors import MVError

    def boom(args):
        raise MVError("nothing here")
    parser = cli.build_parser()
    assert cli.main(["status"], parser=parser, handlers={"status": boom}) == 2
    assert capsys.readouterr().err.strip() == "error: nothing here"
