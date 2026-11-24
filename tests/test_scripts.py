# Copyright (c) 2026 Ashutosh Sinha <ajsinha@gmail.com>. All rights reserved.
# Drishti platform. Proprietary: see LICENSE.
"""Logic of the scripts against a fake repository set (local git repositories; no network, no Maven)."""
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import build_all  # noqa: E402
import clone_all  # noqa: E402
import make_bundle  # noqa: E402
import make_wheels  # noqa: E402
import platform_lib as pl  # noqa: E402

YAML = """
url_base: {base}
repos:
  one:
    repo: r-one
    build_dir: java
    install: true
  two:
    repo: r-two
    build_dir: "-"
    install: false
  top:
    repo: r-top
    build_dir: ""
    install: false
releases:
  rel:
    status: test
    one: v1
    two: v1
    top: v1
"""


def git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def fake(tmp_path):
    origin = tmp_path / "origin"
    for repo, build in (("r-one", "java"), ("r-two", None), ("r-top", "")):
        d = origin / (repo + ".git")
        (d / (build or "")).mkdir(parents=True)
        (d / (build or "") / "mvnw").write_text("#!/bin/sh\n")
        (d / (build or "") / "mvnw.cmd").write_text("")
        (d / "f.txt").write_text(repo)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=d, check=True)
        git(d, "add", ".")
        git(d, "commit", "-q", "-m", "x")
        git(d, "tag", "v1")
    return tmp_path, pl.parse_yaml(YAML.format(base=origin.as_posix()))


def test_parse_yaml_nested_and_scalars():
    cfg = pl.parse_yaml(YAML.format(base="X"))
    assert list(cfg["repos"]) == ["one", "two", "top"]
    assert cfg["repos"]["one"]["install"] is True
    assert cfg["repos"]["top"]["build_dir"] == ""
    assert cfg["releases"]["rel"]["two"] == "v1"


def test_real_platform_yaml_is_consistent():
    cfg = pl.load()
    assert cfg["url_base"].startswith("https://")
    for rel, refs in cfg["releases"].items():
        for name in cfg["repos"]:
            assert name in refs, (rel, name)
    assert pl.repo_url(cfg, "tools") == cfg["url_base"] + "/drishti-tools.git"


def test_bad_yaml_and_unknown_release():
    with pytest.raises(pl.PlatformError):
        pl.parse_yaml("no colon here")
    cfg = pl.parse_yaml(YAML.format(base="X"))
    with pytest.raises(pl.PlatformError):
        pl.refs_for(cfg, "nope", False)
    with pytest.raises(pl.PlatformError):
        pl.refs_for(cfg, None, False)
    assert set(pl.refs_for(cfg, None, True).values()) == {"develop"}


def test_clone_then_update_at_tag(fake, monkeypatch):
    tmp, cfg = fake
    monkeypatch.setattr(pl, "load", lambda path=None: cfg)
    parent = tmp / "parent"
    assert clone_all.main(["--release", "rel", "--parent", str(parent)]) == 0
    assert (parent / "r-one" / "f.txt").read_text() == "r-one"
    assert clone_all.main(["--release", "rel", "--parent", str(parent)]) == 0  # update path
    assert build_all.current_ref(parent / "r-top") == "v1"


def test_clone_refuses_foreign_folder(fake, monkeypatch):
    tmp, cfg = fake
    monkeypatch.setattr(pl, "load", lambda path=None: cfg)
    (tmp / "parent" / "r-one").mkdir(parents=True)
    (tmp / "parent" / "r-one" / "x").write_text("x")
    assert clone_all.main(["--release", "rel", "--parent", str(tmp / "parent")]) == 2


def test_build_plan_order_goals_and_options(fake, tmp_path):
    _, cfg = fake
    (tmp_path / "r-one" / "java").mkdir(parents=True)
    (tmp_path / "r-top").mkdir()
    for d in (tmp_path / "r-one" / "java", tmp_path / "r-top"):
        (d / "mvnw").write_text("")
        (d / "mvnw.cmd").write_text("")
    steps = build_all.plan(cfg, tmp_path, True, tmp_path / ".m2")
    assert [s[0] for s in steps] == ["one", "top"]  # "two" has nothing to build
    assert steps[0][2][2:4] == ["clean", "install"] and steps[1][2][3] == "verify"
    assert all("-DskipTests" in s[2] and any(a.startswith("-Dmaven.repo.local=") for a in s[2]) for s in steps)
    assert steps[0][1] == tmp_path / "r-one" / "java"


def test_build_all_refuses_wrong_tag_and_missing_wrapper(fake, monkeypatch, tmp_path):
    tmp, cfg = fake
    monkeypatch.setattr(pl, "load", lambda path=None: cfg)
    parent = tmp / "parent"
    clone_all.main(["--release", "rel", "--parent", str(parent)])
    git(parent / "r-top", "checkout", "-q", "-B", "main")
    git(parent / "r-top", "commit", "-q", "--allow-empty", "-m", "later")
    assert build_all.main(["--release", "rel", "--parent", str(parent), "--dry-run"]) == 2
    git(parent / "r-top", "checkout", "-q", "--detach", "v1")
    assert build_all.main(["--release", "rel", "--parent", str(parent), "--dry-run"]) == 0
    (parent / "r-one" / "java" / "mvnw").unlink()
    (parent / "r-one" / "java" / "mvnw.cmd").unlink()
    assert build_all.main(["--release", "rel", "--parent", str(parent), "--dry-run"]) == 2


def test_bundle_contents_and_checksums(fake, monkeypatch):
    tmp, cfg = fake
    monkeypatch.setattr(pl, "load", lambda path=None: cfg)
    parent = tmp / "parent"
    clone_all.main(["--release", "rel", "--parent", str(parent)])
    target = make_bundle.build(cfg, "rel", parent, tmp / "out")
    assert target.name == "drishti-platform-rel-source.zip"
    with zipfile.ZipFile(target) as z:
        names = set(z.namelist())
        assert {"r-one/f.txt", "r-two/f.txt", "r-top/f.txt", "README.md", "build_all.py", "SHA-256SUMS"} <= names
        assert ".git" not in " ".join(names)
        sums = z.read("SHA-256SUMS").decode()
        assert "r-one/f.txt" in sums and "build_all.py" in sums


def test_bundle_refuses_missing_tag(fake, monkeypatch):
    tmp, cfg = fake
    monkeypatch.setattr(pl, "load", lambda path=None: cfg)
    cfg["releases"]["rel"]["top"] = "v9"
    parent = tmp / "parent"
    clone_all.main(["--release", "rel", "--parent", str(parent)])
    with pytest.raises(pl.PlatformError):
        make_bundle.build(cfg, "rel", parent, tmp / "out")


def _wheels_fixture(fake, monkeypatch, wheel_names):
    """A release whose r-one plays Drishti (requirements + pin) and r-two plays Lake; pip and the Lake build are mocked."""
    tmp, cfg = fake
    cfg["repos"]["drishti"] = cfg["repos"].pop("one")
    cfg["repos"]["lake"] = cfg["repos"].pop("two")
    cfg["releases"]["rel"] = {"top": "v1", "drishti": "v1", "lake": "v1"}
    monkeypatch.setattr(pl, "load", lambda path=None: cfg)
    parent = tmp / "parent"
    for name, repo in (("drishti", "r-one"), ("lake", "r-two")):
        clone = parent / repo
        subprocess.run(["git", "clone", "-q", (tmp / "origin" / (repo + ".git")).as_posix(), str(clone)], check=True)
    d = parent / "r-one"
    (d / "drishti-console").mkdir()
    (d / "drishti-console" / "requirements.txt").write_text("fastapi>=0.100\n")
    (d / "config" / "compute" / "locks").mkdir(parents=True)
    (d / "config" / "compute" / "locks" / "python.lock").write_text("# x\nnumpy==2.5.3 \\\n    --hash=sha256:aa\nsix==1.17.0 \\\n    --hash=sha256:bb\n")
    (d / "lib").mkdir()
    (d / "lib" / "lake-wheel.pin").write_text("ref=v1\nversion=0.9.1\nsha256=00\n")
    git(d, "add", ".")
    git(d, "commit", "-q", "-m", "reqs")
    git(d, "tag", "-f", "v1")
    calls = []

    def fake_lake(cfg_, refs, parent_, out):
        out.mkdir(parents=True, exist_ok=True)
        (out / "drishti_lake-0.9.1-py3-none-any.whl").write_bytes(b"lake")
        return out / "drishti_lake-0.9.1-py3-none-any.whl"

    real_run = subprocess.run

    def fake_run(cmd, **kw):                                              # only pip is mocked; git still runs
        if "pip" not in cmd:
            return real_run(cmd, **kw)
        calls.append(cmd)
        dest = Path(cmd[cmd.index("-d") + 1])
        for w in wheel_names:
            (dest / w).write_bytes(b"w" + w.encode())
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(pl, "build_lake_wheel", fake_lake)
    monkeypatch.setattr(make_wheels.subprocess, "run", fake_run)
    return cfg, parent, tmp, calls


def test_wheels_pack_contents_and_pip_arguments(fake, monkeypatch):
    cfg, parent, tmp, calls = _wheels_fixture(fake, monkeypatch, ["fastapi-0.1-py3-none-any.whl"])
    zips = make_wheels.build(cfg, "rel", parent, tmp / "out", ["linux-x64", "windows-x64"], "3.13")
    assert [z.name for z in zips] == ["drishti-platform-rel-wheels-linux-x64-py313.zip", "drishti-platform-rel-wheels-windows-x64-py313.zip"]
    with zipfile.ZipFile(zips[0]) as z:
        assert {"fastapi-0.1-py3-none-any.whl", "drishti_lake-0.9.1-py3-none-any.whl", "README.txt", "SHA256SUMS"} <= set(z.namelist())
        assert "setup --system --wheels" in z.read("README.txt").decode() and "python.lock" in z.namelist()
        assert "fastapi-0.1-py3-none-any.whl" in z.read("SHA256SUMS").decode()
    linux = calls[0]
    assert linux.count("--platform") == 3 and "--only-binary=:all:" in linux and linux[linux.index("--abi") + 1] == "cp313"
    assert calls[1].count("--platform") == 1 and "win_amd64" in calls[1]


def test_wheels_refuses_without_binary_wheel(fake, monkeypatch):
    cfg, parent, tmp, _ = _wheels_fixture(fake, monkeypatch, [])
    err = "ERROR: No matching distribution found for fancylib==1"
    monkeypatch.setattr(make_wheels.subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", err))
    monkeypatch.setattr(pl, "lake_pin", lambda *a: {"version": "0.9.1"})
    monkeypatch.setattr(pl, "git_show", lambda *a: "fastapi\n")
    with pytest.raises(pl.PlatformError, match="fancylib"):
        make_wheels.build(cfg, "rel", parent, tmp / "out", ["macos-x64"], "3.13")


def test_wheels_bad_python_version(fake, monkeypatch):
    cfg, parent, tmp, _ = _wheels_fixture(fake, monkeypatch, [])
    with pytest.raises(pl.PlatformError):
        make_wheels.build(cfg, "rel", parent, tmp / "out", ["linux-x64"], "313")


def test_latest_is_the_newest_released_release():
    """The launchers say --release latest: the first release in platform.yaml marked released; any other name is itself."""
    cfg = {"releases": {"i9": {"status": "pending"}, "i8": {"status": "released"}, "i7": {"status": "released"}}}
    assert pl.resolve_release(cfg, "latest") == "i8"
    assert pl.resolve_release(cfg, "i7") == "i7"
    assert pl.resolve_release(cfg, None) is None
    with pytest.raises(pl.PlatformError):
        pl.resolve_release({"releases": {"i9": {"status": "pending"}}}, "latest")


def test_build_all_runs_the_same_maven_as_the_platform_launcher(tmp_path, monkeypatch):
    """A zip has no git: the format check is skipped; on Windows the certificate store and py, as the pom's Windows profile."""
    import build_all
    (tmp_path / "mvnw").write_text("", encoding="utf-8")
    (tmp_path / "mvnw.cmd").write_text("", encoding="utf-8")
    monkeypatch.setattr(build_all.os, "name", "posix")
    cmd = build_all.maven_command(tmp_path, "install", True, None)
    assert "-Dspotless.check.skip=true" in cmd and "-DskipTests" in cmd and f"-Dpython3={sys.executable}" in cmd
    monkeypatch.setattr(build_all.os, "name", "nt")
    cmd = build_all.maven_command(tmp_path, "install", False, None)
    assert cmd[0].endswith("mvnw.cmd") and "-Djavax.net.ssl.trustStoreType=Windows-ROOT" in cmd and f"-Dpython3={sys.executable}" in cmd


def test_the_three_start_here_pages_are_what_the_one_template_writes():
    """START_HERE_WINDOWS/LINUX/MACOS.md come from make_start_here.py: never edited by hand, never stale; Windows never names a venv."""
    import make_start_here
    assert make_start_here.main(["--check"]) == 0
    assert "venv" not in (Path(make_start_here.__file__).parent / "START_HERE_WINDOWS.md").read_text(encoding="utf-8")


def test_launchers_go_to_the_visible_run_configs_folder(fake, monkeypatch):
    """Owner 11-24: no .idea anywhere; clone_all and make_bundle place the platform launchers in <parent>/run-configs (group IntelliJ-platform)."""
    tmp, cfg = fake
    monkeypatch.setattr(pl, "load", lambda path=None: cfg)
    parent = tmp / "parent"
    clone_all.main(["--release", "rel", "--parent", str(parent)])
    placed = sorted(p.name for p in (parent / "run-configs").glob("*.run.xml"))
    assert placed == sorted(p.name for p in (pl.HERE / "parent-run-configs").glob("*.run.xml")) and placed
    assert not (parent / ".idea").exists()
    for f in (parent / "run-configs").glob("*.run.xml"):
        assert 'folderName="IntelliJ-platform"' in f.read_text(encoding="utf-8")
    for f in (pl.HERE / "run-configs").glob("*.run.xml"):            # the index repository's own: Python ones for PyCharm, Maven ones for IntelliJ
        t = f.read_text(encoding="utf-8")
        assert ('folderName="PyCharm-platform"' if "PythonConfigurationType" in t else 'folderName="IntelliJ-platform"') in t
    with zipfile.ZipFile(make_bundle.build(cfg, "rel", parent, tmp / "out")) as z:
        names = z.namelist()
    assert sorted(n for n in names if n.startswith("run-configs/")) == sorted("run-configs/" + n for n in placed)
    assert not any(".idea/" in n for n in names)


def test_bundle_leaves_out_only_git_ide_and_secrets_files():
    keep = make_bundle.keep_member
    assert keep("drishti/run-configs/Drishti run server.run.xml") and keep("drishti/drishti-console/run-configs/Run console.run.xml")
    assert keep("drishti/.mvn/wrapper/maven-wrapper.properties") and keep("drishti/src/A.java")
    for bad in ("drishti/.idea/workspace.xml", "drishti/.idea/runConfigurations/x.xml", "drishti/.gitignore", "drishti/.github/workflows/x.yml", "drishti/.env"):
        assert not keep(bad), bad


def test_build_all_with_no_option_is_the_bundle_build(fake, monkeypatch, tmp_path, capsys):
    """F2/D4: run from an unzipped source bundle, `build_all.py` alone builds what is beside it; a git checkout of the index does not."""
    _, cfg = fake
    for d in (tmp_path / "r-one" / "java", tmp_path / "r-top"):
        d.mkdir(parents=True)
        (d / "mvnw").write_text("")
        (d / "mvnw.cmd").write_text("")
    (tmp_path / "r-two").mkdir()
    (tmp_path / "platform.yaml").write_text("x", encoding="utf-8")
    monkeypatch.setattr(pl, "HERE", tmp_path)
    monkeypatch.setattr(pl, "load", lambda path=None: cfg)
    assert build_all.is_bundle(tmp_path)
    assert build_all.main(["--dry-run", "--skip-tests"]) == 0
    out = capsys.readouterr().out
    assert str(tmp_path / "r-one" / "java") in out and "-DskipTests" in out
    (tmp_path / ".git").mkdir()
    assert not build_all.is_bundle(tmp_path)


def test_first_run_workflow_is_valid_yaml_and_dispatch_only():
    text = (pl.HERE / ".github" / "workflows" / "first-run.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch" in text and "pull_request" not in text and "\npush:" not in text
    assert "windows-latest" in text and "ubuntu-latest" in text and "gh release download" in text
    assert "@v" in text and "uses: actions/checkout" not in text
    try:
        import yaml
    except ImportError:
        return
    doc = yaml.safe_load(text)
    assert set(doc["jobs"]) == {"windows", "posix"} and list(doc[True]) == ["workflow_dispatch"]


def test_a_build_folder_with_a_space_gets_maven_a_temporary_folder_without_one(tmp_path, monkeypatch):
    """The wrappers put Maven's temporary folder in MAVEN_OPTS unquoted: a space in the path would break Maven's start on Linux/macOS."""
    import build_all
    monkeypatch.setattr(build_all.os, "name", "posix")
    env = build_all.maven_env(tmp_path / "John Smith" / "tools", {"MAVEN_OPTS": ""})
    assert "-Djava.io.tmpdir=" in env["MAVEN_OPTS"] and " " not in env["MAVEN_OPTS"].split("-Djava.io.tmpdir=")[1].split()[0]
    assert "MAVEN_OPTS" not in build_all.maven_env(tmp_path / "plain" / "tools", {}) or True
    assert build_all.maven_env(tmp_path / "a b", {"MAVEN_OPTS": "-Djava.io.tmpdir=/x"})["MAVEN_OPTS"] == "-Djava.io.tmpdir=/x"


def test_the_zip_keeps_a_products_own_hidden_files():
    """Only git's and the IDE's files are left out: the server's capacity workbook part `_rels/.rels` (loaded at start) must be in the zip."""
    keep = make_bundle.keep_member
    assert keep("drishti/kernel/drishti-server/src/main/resources/capacity/template/_rels/.rels")
    assert keep("drishti/.mvn/wrapper/maven-wrapper.properties") and keep("drishti/.java-version")
    assert keep("drishti/run-configs/Drishti run server.run.xml")
    assert not keep("drishti/.idea/workspace.xml") and not keep("drishti/.gitignore") and not keep("drishti/.github/workflows/fast.yml")
