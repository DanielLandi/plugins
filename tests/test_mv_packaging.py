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
    assert plugin["version"] == entry["version"] == musicvideo.__version__ == "0.2.1"
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


def test_the_cli_never_writes_bytecode_into_the_plugin():
    # The installed plugin folder is replaced on update and must stay untouched: no __pycache__ there.
    src = (MV / "scripts" / "music-video.py").read_text(encoding="utf-8")
    assert src.index("sys.dont_write_bytecode = True") < src.index("from musicvideo")


def test_every_command_has_a_handler():
    from musicvideo import cli
    sub = next(a for a in cli.build_parser()._actions if a.dest == "command")
    assert set(sub.choices) - set(cli.HANDLERS) == set()


def test_every_text_io_names_its_encoding():
    # Windows defaults to a legacy code page: every text read/write and text subprocess says utf-8.
    import ast
    misses = []
    for f in sorted((MV / "scripts").rglob("*.py")):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "attr", getattr(node.func, "id", ""))
            keys = {k.arg for k in node.keywords}
            text_run = name == "run" and any(k.arg == "text" for k in node.keywords)
            if (name in ("read_text", "write_text") or text_run) and "encoding" not in keys:
                misses.append(f"{f.relative_to(MV)}:{node.lineno}")
    assert misses == []
