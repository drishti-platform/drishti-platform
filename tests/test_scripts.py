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
