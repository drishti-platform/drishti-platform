# Copyright (c) 2026 Ashutosh Sinha <ajsinha@gmail.com>. All rights reserved.
# Drishti platform. Proprietary: see LICENSE.
"""Clone or update every platform repository into a parent folder, at a release's tags or at develop.

python clone_all.py --release i7b [--parent <folder>] [--dry-run]
python clone_all.py --develop
Python 3.10+, git on the PATH. Works on Windows and Linux.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import platform_lib as pl


def git(args: list[str], cwd: Path | None = None, dry: bool = False) -> None:
    print("  git " + " ".join(args))
    if dry:
        return
    result = subprocess.run(["git", *args], cwd=cwd)
    if result.returncode != 0:
        raise pl.PlatformError(f"git {' '.join(args)} failed (exit {result.returncode})")


def clone_or_update(cfg: dict, name: str, ref: str, parent: Path, dry: bool) -> Path:
    folder = parent / cfg["repos"][name]["repo"]
    print(f"{name}: {ref}")
    if not (folder / ".git").exists():
        if folder.exists() and any(folder.iterdir()):
            raise pl.PlatformError(f"{folder} exists and is not a git repository")
        git(["clone", pl.repo_url(cfg, name), str(folder)], dry=dry)
    else:
        git(["fetch", "--tags", "--prune", "origin"], cwd=folder, dry=dry)
    if ref in ("main", "develop") or ref.startswith("wip/"):
        git(["checkout", ref], cwd=folder, dry=dry)
        git(["pull", "--ff-only", "origin", ref], cwd=folder, dry=dry)
    else:
        git(["checkout", "--detach", f"refs/tags/{ref}"], cwd=folder, dry=dry)
    return folder


def place_pom(parent: Path, dry_run: bool) -> None:
    """The platform pom.xml beside the repositories: `mvn` in the parent folder builds tools, Rachana, Lake and Drishti in order."""
    src = Path(__file__).resolve().parent / "pom.xml"
    print(f"  copy {src} -> {parent / 'pom.xml'}")
    if not dry_run:
        shutil.copyfile(src, parent / "pom.xml")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--release", help="a release name from platform.yaml")
    p.add_argument("--develop", action="store_true", help="every repository at develop")
    p.add_argument("--parent", type=Path, default=pl.default_parent(), help="parent folder (default: the folder above this repository)")
    p.add_argument("--dry-run", action="store_true", help="print the git commands only")
    a = p.parse_args(argv)
    try:
        cfg = pl.load()
        refs = pl.refs_for(cfg, a.release, a.develop)
        if not a.dry_run:
            a.parent.mkdir(parents=True, exist_ok=True)
        for name, ref in refs.items():
            clone_or_update(cfg, name, ref, a.parent, a.dry_run)
        place_pom(a.parent, a.dry_run)
    except pl.PlatformError as e:
        return pl.fail(e)
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
