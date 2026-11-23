# Copyright (c) 2026 Ashutosh Sinha <ajsinha@gmail.com>. All rights reserved.
# Drishti platform. Proprietary: see LICENSE.
"""Shared by clone_all.py, build_all.py, make_bundle.py and make_wheels.py: reads platform.yaml (a subset of YAML, standard library only)."""
from __future__ import annotations

import hashlib
import io
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


class PlatformError(Exception):
    """A problem the user can fix; the scripts print the message and exit 2."""


def _scalar(text: str):
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    if text in ("true", "false"):
        return text == "true"
    return text


def parse_yaml(text: str) -> dict:
    """Nested maps by indentation, scalars, # comment lines. Nothing else is supported (on purpose)."""
    root: dict = {}
    stack = [(-1, root)]
    for number, raw in enumerate(text.splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        body = raw.strip()
        if ":" not in body:
            raise PlatformError(f"platform.yaml line {number}: expected 'key: value'")
        key, _, value = body.partition(":")
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if not stack:
            raise PlatformError(f"platform.yaml line {number}: bad indentation")
        parent = stack[-1][1]
        if value.strip() == "":
            child: dict = {}
            parent[key.strip()] = child
            stack.append((indent, child))
        else:
            parent[key.strip()] = _scalar(value)
    return root


def load(path: Path | None = None) -> dict:
    path = path or HERE / "platform.yaml"
    if not path.is_file():
        raise PlatformError(f"{path} not found")
    data = parse_yaml(path.read_text(encoding="utf-8"))
    for need in ("url_base", "repos", "releases"):
        if need not in data:
            raise PlatformError(f"platform.yaml has no '{need}'")
    return data


def repo_url(cfg: dict, name: str) -> str:
    return f"{cfg['url_base'].rstrip('/')}/{cfg['repos'][name]['repo']}.git"


def refs_for(cfg: dict, release: str | None, develop: bool) -> dict:
    """The ref (tag or branch) of every repository, in install order."""
    names = list(cfg["repos"])
    if develop:
        return {n: "develop" for n in names}
    if not release:
        raise PlatformError("give --release <name> (or --develop); known: " + ", ".join(cfg["releases"]))
    if release not in cfg["releases"]:
        raise PlatformError(f"unknown release '{release}'; known: " + ", ".join(cfg["releases"]))
    rel = cfg["releases"][release]
    missing = [n for n in names if n not in rel]
    if missing:
        raise PlatformError(f"release '{release}' names no tag for: {', '.join(missing)}")
    return {n: rel[n] for n in names}


def default_parent() -> Path:
    return HERE.parent


def fail(error: Exception) -> int:
    print(f"error: {error}", file=sys.stderr)
    return 2


def archive(folder: Path, ref: str) -> bytes:
    """git archive of <ref> in <folder> (a tar)."""
    check = subprocess.run(["git", "rev-parse", "--verify", "--quiet", ref + "^{commit}"], cwd=folder, capture_output=True)
    if check.returncode != 0:
        raise PlatformError(f"{folder.name}: '{ref}' does not exist yet")
    out = subprocess.run(["git", "archive", "--format=tar", ref], cwd=folder, capture_output=True)
    if out.returncode != 0:
        raise PlatformError(f"git archive failed in {folder}: {out.stderr.decode(errors='replace')}")
    return out.stdout


def git_show(folder: Path, ref: str, path: str) -> str:
    """A file's text at a ref, read from git (never the working tree)."""
    r = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=folder, capture_output=True, text=True)
    if r.returncode != 0:
        raise PlatformError(f"{folder.name}: {path} not found at {ref}: {r.stderr.strip()}")
    return r.stdout


def lake_pin(cfg: dict, refs: dict, parent: Path) -> dict:
    """drishti/lib/lake-wheel.pin at the Drishti ref: ref, version, sha256."""
    text = git_show(parent / cfg["repos"]["drishti"]["repo"], refs["drishti"], "lib/lake-wheel.pin")
    return dict(l.split("=", 1) for l in text.splitlines() if l and not l.startswith("#") and "=" in l)


def build_lake_wheel(cfg: dict, refs: dict, parent: Path, out: Path) -> Path:
    """Build the pinned Lake wheel from the Lake checkout at the pin's ref (uv build is reproducible), check its SHA-256 against the
    pin, and leave it in <out>."""
    pin = lake_pin(cfg, refs, parent)
    lake = parent / cfg["repos"]["lake"]["repo"]
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "lake"
        with tarfile.open(fileobj=io.BytesIO(archive(lake, pin["ref"]))) as tar:
            tar.extractall(src, filter="data")
        built = Path(tmp) / "wheels"
        r = subprocess.run(["uv", "build", "--wheel", str(src / "python"), "--out-dir", str(built)], capture_output=True, text=True)
        if r.returncode != 0:
            raise PlatformError(f"the Lake wheel did not build (uv build): {r.stderr.strip()[-400:]}")
        wheel = built / f"drishti_lake-{pin['version']}-py3-none-any.whl"
        data = wheel.read_bytes()
    if hashlib.sha256(data).hexdigest() != pin["sha256"]:
        raise PlatformError(f"the Lake wheel built from {pin['ref']} is not the one Drishti pins (sha256 {pin['sha256']})")
    target = out / wheel.name
    target.write_bytes(data)
    return target
