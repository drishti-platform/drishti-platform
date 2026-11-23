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
        assert "setup --system --wheels" in z.read("README.txt").decode()
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
