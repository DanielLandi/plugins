from conftest import REPO

MV = REPO / "music-video"


def _read(p):
    return (MV / p).read_text(encoding="utf-8")


def test_files_exist():
    for name in ("LICENSE", "README.md", "CHANGELOG.md", "SECURITY.md", "THIRD_PARTY_NOTICES.md", ".gitattributes", ".gitignore"):
        assert (MV / name).is_file(), name


def test_licence_and_notices():
    assert _read("LICENSE").startswith("MIT License")
    notices = _read("THIRD_PARTY_NOTICES.md")
    for must in ("remotion-transitions", "CC0", "Quaternius", "Kenney", "Outfit", "OFL", "three.js", "Remotion", "three-vrm", "pixiv"):
        assert must in notices, must
    for model in (MV / "studio/assets/models").glob("*.glb"):
        assert model.name in notices, model.name


def test_readme_says_remotion_licence_and_suno_rules():
    readme = _read("README.md")
    head = readme[:2500]
    assert "Remotion" in head and "licen" in head.lower()
    for must in ("/plugin marketplace add DanielLandi/plugins", "/plugin install music-video@daniellandi",
                 "doctor", "your own Suno account", "macOS"):
        assert must in readme, must


def test_gitattributes_and_ignore():
    attrs = _read(".gitattributes")
    assert "*.glb binary" in attrs and "studio/transitions/** linguist-vendored" in attrs
    ignore = _read(".gitignore")
    for must in ("node_modules/", ".env*"):
        assert must in ignore
    assert ".private-terms.txt" in (REPO / ".gitignore").read_text(encoding="utf-8")


def test_root_docs_list_the_plugin():
    assert "music-video" in (REPO / "README.md").read_text(encoding="utf-8")
    agents = (REPO / "AGENTS.md").read_text(encoding="utf-8")
    assert "music-video" in agents and ".private-terms.txt" in agents
    assert "Suno" in (REPO / "SERVICES.md").read_text(encoding="utf-8")


def test_docs_name_the_install_folder_not_the_cache():
    for name in ("README.md", "THIRD_PARTY_NOTICES.md"):
        text = _read(name)
        assert "into the cache" not in text, name
    assert "Application Support" in _read("README.md")
    assert "upgrad" in _read("CHANGELOG.md").lower()  # 0.1.0 users are told what moved


def test_engine_pins_three_vrm():
    import json
    pkg = json.loads(_read("studio/package.json"))
    assert pkg["dependencies"]["@pixiv/three-vrm"] == "3.5.5"
    lock = json.loads(_read("studio/package-lock.json"))
    assert lock["packages"]["node_modules/@pixiv/three-vrm"]["version"] == "3.5.5"
    override = _read("studio/webpack-override.ts")
    assert "vrm" in override and "@mv/avatars" in override and "MV_AVATARS" in override
    assert "*.vrm" in _read("studio/types/assets.d.ts")
    stub = _read("studio/tools/stub-assets.ts")  # the Node tools that import a video's modules stub model files
    assert "vrm" in stub and "@mv/avatars/" in stub
    for tool in ("tools/board.ts", "tools/web.ts"):
        assert "stubModelFiles()" in _read(f"studio/{tool}"), tool
    assert "**/*.vrm" in _read("studio/tools/web.ts") and "@mv\\/avatars" in _read("studio/tools/web.ts")
    assert not list((MV / "studio").rglob("*.vrm")), "avatars are downloaded, never in the repo"
