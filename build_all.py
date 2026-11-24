# Copyright (c) 2026 Ashutosh Sinha <ajsinha@gmail.com>. All rights reserved.
# Drishti platform. Proprietary: see LICENSE.
"""Build and install every platform repository in order (tools, Rachana, Lake), then build Drishti. Uses each repository's mvnw / mvnw.cmd.

python build_all.py --release i7b [--parent <folder>] [--repo-local] [--skip-tests] [--dry-run]
python build_all.py [--skip-tests]            (no option, run from an unzipped source bundle: the same as --bundle .)
python build_all.py --bundle <unzipped source bundle folder> [--skip-tests]
Tests are opt-out and explicit: they run unless --skip-tests is given.
--release   checks that each repository is at the release's tag (clone_all.py puts it there); --bundle builds what is in the folder.
--repo-local  a dedicated Maven repository <parent>/.m2-drishti instead of ~/.m2.
Python 3.10+, JDK 21 (JAVA_HOME). No bash, no .exe, no Maven install (each repository's wrapper). The same build as the
platform pom's IntelliJ launcher platform-clean-install: on Windows the Windows certificate store and py, the format check skipped.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import platform_lib as pl


def is_bundle(folder: Path) -> bool:
    """platform.yaml with the product folders beside it and no git checkout of the index repository: an unzipped source bundle."""
    if not (folder / "platform.yaml").is_file() or (folder / ".git").exists():
        return False
    try:
        cfg = pl.load(folder / "platform.yaml")
    except Exception:
        return False
    return all((folder / spec["repo"]).is_dir() for spec in cfg["repos"].values())


def current_ref(folder: Path) -> str:
    out = subprocess.run(["git", "describe", "--tags", "--exact-match"], cwd=folder, capture_output=True, text=True)
    if out.returncode == 0:
        return out.stdout.strip()
    out = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=folder, capture_output=True, text=True)
    return out.stdout.strip() or "?"


def maven_command(build_dir: Path, goal: str, skip_tests: bool, repo_local: Path | None) -> list[str]:
    wrapper = build_dir / ("mvnw.cmd" if os.name == "nt" else "mvnw")
    if not wrapper.is_file():
        raise pl.PlatformError(f"{wrapper} not found (is the repository complete?)")
    cmd = [str(wrapper), "-B", "clean", goal, "-Dspotless.check.skip=true"]   # as the platform pom: a zip has no git for the format check
    if os.name == "nt":                     # as the pom's Windows profile: the company proxy's root certificate, and py (not the Store stub)
        cmd += ["-Djavax.net.ssl.trustStoreType=Windows-ROOT", "-Dpython3=py"]
    if skip_tests:
        cmd.append("-DskipTests")
    if repo_local:
        cmd.append(f"-Dmaven.repo.local={repo_local}")
    return cmd


def maven_env(build_dir: Path, environ: dict | None = None) -> dict:
    """The environment of one Maven run. On Linux and macOS the tools' and Lake's wrappers put Maven's temporary folder under the build folder
    in MAVEN_OPTS, unquoted: a folder name with a space then breaks Maven's start ("Could not find or load main class"). Such a path gets a
    temporary folder of the system's instead, given here, so the wrapper keeps it."""
    env = dict(os.environ if environ is None else environ)
    if os.name != "nt" and " " in str(build_dir) and "-Djava.io.tmpdir=" not in env.get("MAVEN_OPTS", ""):
        import tempfile
        tmp = Path(tempfile.gettempdir()) / f"drishti-maven-{os.getuid()}"
        tmp.mkdir(parents=True, exist_ok=True)
        env["MAVEN_OPTS"] = f"-Djava.io.tmpdir={tmp} " + env.get("MAVEN_OPTS", "")
    return env


def plan(cfg: dict, parent: Path, skip_tests: bool, repo_local: Path | None) -> list[tuple[str, Path, list[str]]]:
    steps = []
    for name, spec in cfg["repos"].items():
        if spec["build_dir"] == "-":
            continue
        folder = parent / spec["repo"]
        build_dir = folder / spec["build_dir"] if spec["build_dir"] else folder
        steps.append((name, build_dir, maven_command(build_dir, "install" if spec["install"] else "verify", skip_tests, repo_local)))
    return steps


def check_refs(cfg: dict, parent: Path, refs: dict) -> None:
    for name, ref in refs.items():
        folder = parent / cfg["repos"][name]["repo"]
        if not folder.is_dir():
            raise pl.PlatformError(f"{folder} not found: run clone_all.py first")
        found = current_ref(folder)
        if found != ref:
            raise pl.PlatformError(f"{name} is at '{found}' but the release needs '{ref}': run clone_all.py --release ...")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--release", help="a release name from platform.yaml")
    p.add_argument("--bundle", type=Path, help="folder of an unzipped source bundle")
    p.add_argument("--parent", type=Path, default=pl.default_parent())
    p.add_argument("--repo-local", action="store_true", help="dedicated Maven repository <parent>/.m2-drishti")
    p.add_argument("--skip-tests", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="print the commands only")
    a = p.parse_args(argv)
    if not a.bundle and not a.release and is_bundle(pl.HERE):     # run from an unzipped source bundle: build what is beside this file
        a.bundle = pl.HERE
    try:
        if a.bundle:
            parent = a.bundle.resolve()
            cfg = pl.load(parent / "platform.yaml")
        else:
            parent = a.parent.resolve()
            cfg = pl.load()
            check_refs(cfg, parent, pl.refs_for(cfg, a.release, False))
        local = parent / ".m2-drishti" if a.repo_local else None
        steps = plan(cfg, parent, a.skip_tests, local)
        for name, build_dir, cmd in steps:
            print(f"== {name}: {' '.join(cmd)}   (in {build_dir})")
            if a.dry_run:
                continue
            if subprocess.run(cmd, cwd=build_dir, env=maven_env(build_dir)).returncode != 0:
                raise pl.PlatformError(f"the build of {name} failed; fix it and run again (finished repositories are not repeated if you start from it manually)")
    except pl.PlatformError as e:
        return pl.fail(e)
    print("all built")
    return 0


if __name__ == "__main__":
    sys.exit(main())
