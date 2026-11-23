# Copyright (c) 2026 Ashutosh Sinha <ajsinha@gmail.com>. All rights reserved.
# Drishti platform. Proprietary: see LICENSE.
"""Build drishti-platform-<release>-wheels-<target>-py<NN>.zip: every Python wheel the Drishti console needs on one platform and
Python version (its requirements.txt at the release tag, plus the pinned Lake wheel and its dependencies), README.txt and SHA256SUMS.

python make_wheels.py --release i7c --parent <folder> --out <folder> [--target windows-x64|linux-x64|macos-arm64|macos-x64|all] [--python 3.13]
Needs the repositories cloned in the parent folder (clone_all.py), pip, uv and network access to PyPI. Use on the offline machine:
    py tools\\drishti.py setup --system --wheels <unzipped folder or the zip>
"""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import platform_lib as pl

PLATFORMS = {
    "windows-x64": ["win_amd64"],
    "linux-x64": ["manylinux2014_x86_64", "manylinux_2_17_x86_64", "manylinux_2_28_x86_64"],
    "macos-arm64": ["macosx_11_0_arm64", "macosx_12_0_arm64", "macosx_14_0_arm64"],
    "macos-x64": ["macosx_10_15_x86_64", "macosx_11_0_x86_64", "macosx_12_0_x86_64"],
}
REQUIREMENTS = "drishti-console/requirements.txt"
LOCK = "config/compute/locks/python.lock"

README = """Drishti platform {release}: Python wheels for {target}, Python {python}

What it is: every wheel the Drishti console needs on this platform ({tags}) and CPython {python},
downloaded from PyPI as binary wheels, plus the pinned Drishti Lake wheel ({lake}) and its dependencies.
Nothing needs a compiler or the network.

How to use (on the offline machine, from the unzipped source bundle):
    py tools\\drishti.py setup --system --wheels <this zip or the folder you unzipped it to>
    (Linux and macOS: python3 tools/drishti.py setup --system --wheels <zip or folder>)

The pack carries two requirement files, and setup installs both: requirements.txt (the console, with the Lake wheel) and python.lock
(the server's compute lock: numpy, pandas, pyarrow, scipy ..., checked against the system interpreter before any Python run).
They were resolved together, so they agree.

Or by hand, into any Python {python} (python.lock first: it is hash-checked, so pip takes it on its own):
    python -m pip install --no-index --find-links <folder> -r python.lock
    python -m pip install --no-index --find-links <folder> {lake_req} -r requirements.txt

Wheels: {count}. Each file's SHA-256 is in SHA256SUMS.
"""


def pip_command() -> list[str]:
    """This Python's pip, or (a Python without pip, such as a distribution's system Python) pip run through uv."""
    if subprocess.run([sys.executable, "-c", "import pip"], capture_output=True).returncode == 0:
        return [sys.executable, "-m", "pip"]
    if shutil.which("uv"):
        return ["uv", "run", "--no-project", "--with", "pip", "python", "-m", "pip"]
    raise pl.PlatformError("pip is not available for this Python (install pip, or uv)")


def pip_download(requirements: list[str], dest: Path, target: str, python: str) -> None:
    """pip download of binary wheels only, for the target's platform tags; refuses in words when a requirement has none."""
    abi = "cp" + python.replace(".", "")
    cmd = [*pip_command(), "download", "--only-binary=:all:", "--python-version", python, "--implementation", "cp",
           "--abi", abi, "-d", str(dest), "--disable-pip-version-check", "--no-input"]
    for tag in PLATFORMS[target]:
        cmd += ["--platform", tag]
    cmd += requirements
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        err = r.stderr.strip()
        missing = [l.strip() for l in err.splitlines() if "No matching distribution" in l or "Could not find a version" in l]
        what = "; ".join(missing) if missing else err[-600:]
        raise pl.PlatformError(f"no binary wheel for {target} / Python {python}: {what}")


def build_one(cfg: dict, release: str, parent: Path, out_dir: Path, target: str, python: str, lake_dir: Path | None = None) -> Path:
    refs = pl.refs_for(cfg, release, False)
    drishti = parent / cfg["repos"]["drishti"]["repo"]
    if not drishti.is_dir():
        raise pl.PlatformError(f"{drishti} not found: run clone_all.py first")
    requirements = pl.git_show(drishti, refs["drishti"], REQUIREMENTS)
    lock = pl.git_show(drishti, refs["drishti"], LOCK)                      # the server's compute lock, pins with hashes
    pins = "".join(m.group(1) + "\n" for m in re.finditer(r"^([A-Za-z0-9_.\-]+==[^\s\\]+)", lock, re.M))
    pin = pl.lake_pin(cfg, refs, parent)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        lake = pl.build_lake_wheel(cfg, refs, parent, work / "lake") if lake_dir is None else next(lake_dir.glob("drishti_lake-*.whl"))
        (work / "requirements.txt").write_text(requirements, encoding="utf-8")
        (work / "lock-pins.txt").write_text(pins, encoding="utf-8")        # pip applies hashes only when every requirement has one
        wheels = work / "wheels"
        wheels.mkdir()
        (wheels / lake.name).write_bytes(lake.read_bytes())
        pip_download([str(wheels / lake.name), "-r", str(work / "requirements.txt"), "-r", str(work / "lock-pins.txt")], wheels, target, python)
        files = sorted(wheels.glob("*.whl"))
        sums = "".join(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.name}\n" for f in files)
        readme = README.format(release=release, target=target, python=python, tags=", ".join(PLATFORMS[target]), lake=lake.name,
                               lake_req=f"drishti_lake=={pin['version']}", count=len(files))
        out_dir.mkdir(parents=True, exist_ok=True)
        zpath = out_dir / f"drishti-platform-{release}-wheels-{target}-py{python.replace('.', '')}.zip"
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            def put(name: str, data: bytes) -> None:
                info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                info.external_attr = 0o644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, data)

            for f in files:
                put(f.name, f.read_bytes())
            put("requirements.txt", "".join(l for l in requirements.splitlines(True) if not l.startswith("--find-links")).encode())   # the pack is the link source
            put("python.lock", lock.encode())
            put("README.txt", readme.encode())
            put("SHA256SUMS", sums.encode())
    return zpath


def build(cfg: dict, release: str, parent: Path, out_dir: Path, targets: list[str], python: str) -> list[Path]:
    if not python.replace(".", "").isdigit() or python.count(".") != 1:
        raise pl.PlatformError(f"--python must look like 3.13, not '{python}'")
    refs = pl.refs_for(cfg, release, False)
    with tempfile.TemporaryDirectory() as tmp:                                # the Lake wheel is built once for all targets
        pl.build_lake_wheel(cfg, refs, parent, Path(tmp))
        return [build_one(cfg, release, parent, out_dir, t, python, Path(tmp)) for t in targets]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--release", required=True)
    p.add_argument("--parent", type=Path, default=pl.default_parent())
    p.add_argument("--out", type=Path, default=Path.cwd())
    p.add_argument("--target", default="all", choices=[*PLATFORMS, "all"])
    p.add_argument("--python", default="3.13")
    a = p.parse_args(argv)
    targets = list(PLATFORMS) if a.target == "all" else [a.target]
    try:
        zips = build(pl.load(), a.release, a.parent.resolve(), a.out.resolve(), targets, a.python)
    except pl.PlatformError as e:
        return pl.fail(e)
    for z in zips:
        print(f"{z} ({z.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
