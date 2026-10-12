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
    assert plugin["version"] == entry["version"] == musicvideo.__version__ == "0.2.2"
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


def _text_io_misses(source: str) -> list[int]:
    """Lines of text reads/writes and text subprocesses that do not name their encoding."""
    import ast
    misses = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = getattr(func, "attr", getattr(func, "id", ""))
        keys = {k.arg for k in node.keywords}
        mode_kw = next((k.value.value for k in node.keywords if k.arg == "mode" and isinstance(k.value, ast.Constant)), None)
        if name == "open" and isinstance(func, ast.Name):  # builtin open(file, mode)
            mode = node.args[1].value if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) else mode_kw
        elif name == "open" and isinstance(func, ast.Attribute) and not (
                isinstance(func.value, ast.Name) and func.value.id in {"os", "io", "codecs", "tarfile", "gzip", "webbrowser"}):
            mode = node.args[0].value if node.args and isinstance(node.args[0], ast.Constant) else mode_kw  # Path.open(mode)
        else:
            mode = "b"  # not a file open
        text_open = name == "open" and "b" not in str(mode or "r")
        text_run = name in ("run", "Popen", "check_output") and keys & {"text", "universal_newlines"}
        if (name in ("read_text", "write_text") or text_run or text_open) and "encoding" not in keys:
            misses.append(node.lineno)
    return misses


def test_the_encoding_check_reads_open_modes_right():
    sample = "\n".join(["open(p)", "open(p, 'rb')", "p.open()", "p.open('rb')", "os.open(p, 0)",
                        "subprocess.Popen(c, text=True)", "subprocess.check_output(c)", "p.read_text()",
                        "open(p, 'w', encoding='utf-8')"])
    assert _text_io_misses(sample) == [1, 3, 6, 8]


def test_every_text_io_names_its_encoding():
    # Windows defaults to a legacy code page: every text read/write and text subprocess says utf-8, in the CLI and
    # in the engine's Python tools.
    files = [*sorted((MV / "scripts").rglob("*.py")), *sorted((MV / "studio" / "tools").glob("*.py"))]
    misses = [f"{f.relative_to(MV)}:{n}" for f in files for n in _text_io_misses(f.read_text(encoding="utf-8"))]
    assert misses == []
