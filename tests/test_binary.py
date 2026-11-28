# Copyright (c) 2026 Ashutosh Sinha <ajsinha@gmail.com>. All rights reserved.
# Drishti platform. Proprietary: see LICENSE.
"""The binary release package (make_binary.py) from a fake built Drishti folder: contents, exclusions, manifest, checksums,
reproducibility, and the verifier on the unpacked package. No Maven, no network."""
import hashlib
import json
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import make_binary  # noqa: E402
import platform_lib as pl  # noqa: E402


def _w(p: Path, text: str = "x", mode: int | None = None) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    if mode:
        p.chmod(mode)


@pytest.fixture
def built(tmp_path):
    d = tmp_path / "drishti"
    (d / "lib").mkdir(parents=True)
    with zipfile.ZipFile(d / "lib" / "drishti-server-9.9.9-exec.jar", "w") as z:
        z.writestr("META-INF/build-info.properties", "build.version=9.9.9\nbuild.time=2026-01-01\n")
    (d / "lib" / "drishti-server-exec.jar").write_bytes(b"alias, never shipped")
    _w(d / "lib" / "lake-wheel.pin", "ref=v0.9.1\nversion=0.9.1\nsha256=ab\n")
    _w(d / "modules" / "banking-1.0.0.dmod", "dmod")
    _w(d / "modules" / "first-party.yaml", "modules: []")
    _w(d / "modules" / "banking" / "src" / "A.java", "source of a module: never shipped")
    for f in ("LICENSE", "README.md", "THIRD-PARTY-NOTICES.md"):
        _w(d / f)
    _w(d / "config" / "app.yaml", "a: 1")
    _w(d / "tools" / "drishti.py", "print(1)", 0o755)
    _w(d / "tools" / "test_x.py", "test: never")
    _w(d / "tools" / "__pycache__" / "x.pyc", "pyc")
    _w(d / "tools" / "bench" / "scale.sh", "bench")
    _w(d / "drishti-console" / "run_drishti_web.py", "console")
    _w(d / "drishti-console" / "tests" / "t.py", "tests")
    _w(d / "deploy" / "systemd" / "drishti-server.service", "[Unit]")
    _w(d / "deploy" / "aws" / "x.tf", "aws")
    _w(d / "docs" / "guides" / "G.md", "guide")
    _w(d / "docs" / "publications" / "deck.pptx", "deck")
    _w(d / "clients" / "drishti_client.py", "c")
    _w(d / "data" / "testdata" / "big.jsonl.gz", "demo data: never shipped")
    _w(d / "kernel" / "A.java", "source: never shipped")
    return d


@pytest.fixture
def wheels():
    return {"drishti_lake-0.9.1-py3-none-any.whl": b"whl", "numpy-2.0-cp313-manylinux.whl": b"np", "requirements.txt": b"fastapi\n",
            "python.lock": b"numpy==2.0 \\\n --hash=sha256:00\n", "SHA256SUMS": b""}


def _build(built, wheels, out):
    return make_binary.assemble("rel", "linux-x64", built, wheels, out, {"tools": "v1", "drishti": "v9"}, None)


def _members(path):
    with tarfile.open(path) as t:
        return {m.name: m for m in t.getmembers()}


def test_contents_and_exclusions(built, wheels, tmp_path):
    names = set(_members(_build(built, wheels, tmp_path / "o")))
    top = "drishti-rel-linux-x64/"
    for must in ("drishti/lib/drishti-server-9.9.9-exec.jar", "drishti/lib/lake-wheel.pin", "drishti/lib/ext/README.txt",
                 "drishti/lib/wheels/drishti_lake-0.9.1-py3-none-any.whl", "drishti/modules/banking-1.0.0.dmod", "drishti/modules/first-party.yaml",
                 "drishti/config/app.yaml", "drishti/tools/drishti.py", "drishti/drishti-console/run_drishti_web.py",
                 "drishti/deploy/systemd/drishti-server.service", "drishti/docs/guides/G.md", "drishti/LICENSE",
                 "wheels/requirements.txt", "wheels/python.lock", "wheels/numpy-2.0-cp313-manylinux.whl",
                 "MANIFEST.json", "SHA256SUMS", "INSTALL.md", "verify_package.py"):
        assert top + must in names, must
    for never in ("lib/drishti-server-exec.jar", "modules/banking/src/A.java", "tools/test_x.py", "tools/__pycache__/x.pyc", "tools/bench/scale.sh",
                  "drishti-console/tests/t.py", "deploy/aws/x.tf", "docs/publications/deck.pptx", "data/testdata/big.jsonl.gz", "kernel/A.java"):
        assert top + "drishti/" + never not in names, never


def test_manifest(built, wheels, tmp_path):
    p = _build(built, wheels, tmp_path / "o")
    with tarfile.open(p) as t:
        m = json.load(t.extractfile("drishti-rel-linux-x64/MANIFEST.json"))
    assert m["release"] == "rel" and m["target"] == "linux-x64"
    assert m["drishti"]["version"] == "9.9.9" and m["drishti"]["build"]["build.version"] == "9.9.9"
    assert m["drishti"]["server_jar_sha256"] == hashlib.sha256((built / "lib/drishti-server-9.9.9-exec.jar").read_bytes()).hexdigest()
    assert m["modules"] == {"banking-1.0.0.dmod": hashlib.sha256(b"dmod").hexdigest()}
    assert m["python"]["lake_wheel"] == "drishti_lake-0.9.1-py3-none-any.whl" and m["python"]["lake_pin"]["version"] == "0.9.1"
    assert m["python"]["wheel_count"] == 2 and m["java"]["minimum"] == 21
    assert m["contents"] == {"site_config": False, "demo_data": False, "sources": False}


def test_reproducible_and_normalised(built, wheels, tmp_path):
    a = _build(built, wheels, tmp_path / "a")
    for p in built.rglob("*"):                                   # other modification times and an executable bit elsewhere: same bytes
        if p.is_file():
            p.touch()
    b = _build(built, wheels, tmp_path / "b")
    assert a.read_bytes() == b.read_bytes()
    members = _members(a)
    assert {m.mtime for m in members.values()} == {make_binary.MTIME}
    assert {m.uid for m in members.values()} == {0} and {m.uname for m in members.values()} == {""}
    assert members["drishti-rel-linux-x64/drishti/tools/drishti.py"].mode == 0o755
    assert members["drishti-rel-linux-x64/drishti/config/app.yaml"].mode == 0o644
    assert (a.parent / (a.name + ".sha256")).read_text().split()[0] == hashlib.sha256(a.read_bytes()).hexdigest()


def test_verify_on_the_unpacked_package(built, wheels, tmp_path):
    p = _build(built, wheels, tmp_path / "o")
    with tarfile.open(p) as t:
        t.extractall(tmp_path / "x", filter="data")
    root = tmp_path / "x" / "drishti-rel-linux-x64"
    run = lambda: subprocess.run([sys.executable, "-I", str(root / "verify_package.py")], capture_output=True, text=True)
    ok = run()
    assert ok.returncode == 0 and "package verified" in ok.stdout
    (root / "drishti" / "config" / "app.yaml").write_text("changed")
    (root / "extra.txt").write_text("unlisted")
    bad = run()
    assert bad.returncode != 0 and "app.yaml" in bad.stdout and "extra.txt" in bad.stdout


def test_refusals(built, wheels, tmp_path):
    with pytest.raises(pl.PlatformError, match="exactly one"):
        (built / "lib" / "drishti-server-9.9.8-exec.jar").write_bytes(b"x")
        _build(built, wheels, tmp_path / "o")
    (built / "lib" / "drishti-server-9.9.8-exec.jar").unlink()
    with pytest.raises(pl.PlatformError, match="wheel pack"):
        make_binary.assemble("rel", "linux-x64", built, {"requirements.txt": b""}, tmp_path / "o", {}, None)
    with pytest.raises(pl.PlatformError, match="Linux"):
        make_binary.assemble("rel", "windows-x64", built, wheels, tmp_path / "o", {}, None)
    (built / "modules" / "banking-1.0.0.dmod").unlink()
    with pytest.raises(pl.PlatformError, match="no module packages"):
        _build(built, wheels, tmp_path / "o")


def test_no_site_config_or_secrets_shipped(built, wheels, tmp_path):
    _w(built / "config" / "secrets.env", "TOKEN=1")
    _w(built / "tools" / ".env", "X=1")
    names = " ".join(_members(_build(built, wheels, tmp_path / "o")))
    assert ".env" not in names
