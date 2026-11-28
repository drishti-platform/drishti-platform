# Copyright (c) 2026 Ashutosh Sinha <ajsinha@gmail.com>. All rights reserved.
# Drishti platform. Proprietary: see LICENSE.
"""Build drishti-<release>-<target>.tar.gz: the BINARY release package a production host installs from. No Maven, no compiler and no
source build on that host.

It holds, under one folder drishti-<release>-<target>/:
    drishti/     the install folder (DRISHTI_HOME): the server exec jar (lib/), the module packages (modules/*.dmod, first-party.yaml),
                 the console (Python app files), the operator tools (tools/drishti.py ...), config templates, systemd unit templates
                 (deploy/), the help documents (docs/), licences
    wheels/      the pinned Python libraries (the wheel pack of make_wheels.py: wheels, requirements.txt, python.lock, SHA256SUMS)
    MANIFEST.json  versions of Drishti and of each pinned product, the jar and package hashes, the Python and Java requirements
    SHA256SUMS     every file of the package
    INSTALL.md     the install and upgrade steps;  verify_package.py  checks SHA256SUMS on the host (Python standard library only)
It carries no site configuration (a site's settings live outside the release) and no demo data.

python make_binary.py --release i8 --target linux-x64 [--out <folder>] [--parent <folder>]    one command from the release's tags:
    clones' tags are archived, built once with the platform's build (Maven: on the BUILD machine, never the production host), the wheel
    pack is made (needs PyPI: the build machine), and the package is assembled.
python make_binary.py --release i8 --target linux-x64 --built <built drishti folder> --wheels <wheel pack zip or folder> --out <folder>
    assemble from an already built Drishti folder (CI after build_all.py; a lane's test).
The package is reproducible from the same inputs: sorted entries, fixed times and owners, normalised modes, gzip without a time stamp.
(The jar is the Maven build's: byte-equal when the build is.) Linux x64 only: production is Linux.
"""
from __future__ import annotations

import argparse
import fnmatch
import gzip
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

import platform_lib as pl

TARGETS = ["linux-x64"]
MTIME = 1767225600                       # 2026-01-01T00:00:00Z: the fixed time of every entry
PYTHON = "3.13"
JAVA_MIN = 21

# What goes into drishti/ from a built Drishti folder. A folder not listed is not shipped (sources, tests, demo data, IDE files).
TOP_FILES = ["LICENSE", "THIRD-PARTY-NOTICES.md", "README.md", "RELEASE_NOTES.md", "CHANGELOG.md", "HOW_IT_FITS.md", "HOW_IT_FITS.pdf"]
TOP_DIRS = ["config", "tools", "drishti-console", "deploy", "docs", "clients"]
# patterns (matched on the path relative to the Drishti folder, and on each path part) that never ship
EXCLUDE_PARTS = {"__pycache__", ".pytest_cache", "node_modules", "tests", "run-configs", "mockups", "publications", ".git",
                 ".idea", ".mvn", "target", "aws", "docker"}
EXCLUDE_NAMES = ["secrets.env", "secrets.ini", "*.pyc", "test_*.py", "*_test.py", "conftest.py", ".git*", ".env", "*.iml", "drill*.txt", "drill*.sh"]
EXCLUDE_PATHS = ["tools/drillkit/*", "tools/bench/results/*", "tools/bench/*.sh", "docs/lenses/mockups/*"]   # tools/dev, browser and bench code stay: drishti.py loads them


class BinaryError(pl.PlatformError):
    pass


def keep(rel: str) -> bool:
    parts = rel.split("/")
    if any(p in EXCLUDE_PARTS for p in parts[:-1]) or any(fnmatch.fnmatch(parts[-1], n) for n in EXCLUDE_NAMES):
        return False
    return not any(fnmatch.fnmatch(rel, g) for g in EXCLUDE_PATHS)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def collect(drishti: Path) -> dict[str, tuple[bytes, int]]:
    """Every file of drishti/ in the package: {path under drishti/: (bytes, mode)}. Raises in words when the folder is not built."""
    out: dict[str, tuple[bytes, int]] = {}

    def add(path: Path, rel: str) -> None:
        mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
        out[rel] = (path.read_bytes(), mode)

    jars = sorted(p for p in (drishti / "lib").glob("drishti-server-*-exec.jar") if re.fullmatch(r"drishti-server-\d[^/]*-exec\.jar", p.name))
    if len(jars) != 1:
        raise BinaryError(f"{drishti}/lib holds {len(jars)} versioned server jars (drishti-server-<version>-exec.jar); the package needs exactly one: "
                          "build Drishti first (build_all.py --skip-tests)")
    add(jars[0], "lib/" + jars[0].name)
    for name in ("lake-wheel.pin", "README.md"):
        if (drishti / "lib" / name).is_file():
            add(drishti / "lib" / name, "lib/" + name)
    out["lib/ext/README.txt"] = (b"Your own jars (JDBC drivers, connector plugins) go here. Copy them from the previous release on an upgrade.\n", 0o644)
    dmods = sorted((drishti / "modules").glob("*.dmod"))
    if not dmods or not (drishti / "modules" / "first-party.yaml").is_file():
        raise BinaryError(f"{drishti}/modules holds no module packages (*.dmod) or no first-party.yaml: the build did not finish")
    for p in dmods + [drishti / "modules" / "first-party.yaml"]:
        add(p, "modules/" + p.name)
    for name in TOP_FILES:
        if (drishti / name).is_file():
            add(drishti / name, name)
    for top in TOP_DIRS:
        base = drishti / top
        if not base.is_dir():
            raise BinaryError(f"{base} not found: the folder is not a Drishti checkout")
        for p in sorted(base.rglob("*")):
            rel = p.relative_to(drishti).as_posix()
            if p.is_file() and not p.is_symlink() and keep(rel):
                add(p, rel)
    return out


def wheel_files(pack: Path) -> dict[str, bytes]:
    """The files of a wheel pack given as a zip or an unzipped folder."""
    if pack.is_dir():
        return {p.name: p.read_bytes() for p in sorted(pack.iterdir()) if p.is_file()}
    if not zipfile.is_zipfile(pack):
        raise BinaryError(f"{pack} is neither a wheel pack zip nor a folder")
    with zipfile.ZipFile(pack) as z:
        return {n: z.read(n) for n in sorted(z.namelist()) if not n.endswith("/")}


def jar_facts(jar: bytes) -> dict:
    """The build facts inside the exec jar (META-INF/build-info.properties), when it has them."""
    try:
        with zipfile.ZipFile(io.BytesIO(jar)) as z:
            name = next((n for n in z.namelist() if n.endswith("META-INF/build-info.properties")), None)
            if name:
                return {k.strip(): v.strip() for k, v in (l.split("=", 1) for l in z.read(name).decode("utf-8", "replace").splitlines()
                                                          if "=" in l and not l.startswith("#"))}
    except zipfile.BadZipFile:
        pass
    return {}


def git_commit(folder: Path) -> str | None:
    r = subprocess.run(["git", "-C", str(folder), "rev-parse", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def manifest(release: str, target: str, files: dict[str, tuple[bytes, int]], wheels: dict[str, bytes], refs: dict, cfg: dict | None,
             drishti: Path, python: str) -> dict:
    jar = next(n for n in files if re.fullmatch(r"lib/drishti-server-.*-exec\.jar", n))
    version = re.fullmatch(r"lib/drishti-server-(.*)-exec\.jar", jar).group(1)
    pin = {}
    if "lib/lake-wheel.pin" in files:
        pin = dict(l.split("=", 1) for l in files["lib/lake-wheel.pin"][0].decode().splitlines() if "=" in l and not l.startswith("#"))
    whl = sorted(n for n in wheels if n.endswith(".whl"))
    return {
        "package": "drishti-binary-release",
        "release": release,
        "target": target,
        "drishti": {"version": version, "git_commit": git_commit(drishti), "server_jar": jar.split("/", 1)[1],
                    "server_jar_sha256": sha256(files[jar][0]), "build": jar_facts(files[jar][0])},
        "products": {name: {"ref": ref, "repository": cfg["repos"][name]["repo"] if cfg else name} for name, ref in refs.items()},
        "modules": {n.split("/", 1)[1]: sha256(files[n][0]) for n in sorted(files) if n.startswith("modules/") and n.endswith(".dmod")},
        "python": {"version": python, "wheel_count": len(whl), "lake_wheel": next((w for w in whl if w.startswith("drishti_lake-")), None),
                   "lake_pin": pin, "requirements": "wheels/requirements.txt", "lock": "wheels/python.lock"},
        "java": {"minimum": JAVA_MIN},
        "contents": {"site_config": False, "demo_data": False, "sources": False},
    }


INSTALL = """# Drishti {release} binary package ({target})

Install from this package on a Linux host: no Maven, no compiler, no source build and no internet. The steps with every setting are in
`drishti/docs/guides/OPERATIONS_GUIDE.md`, "Production deployment (Linux)".

What it holds: `drishti/` (the install folder, DRISHTI_HOME), `wheels/` (the pinned Python libraries, offline), `MANIFEST.json` (versions and
hashes), `SHA256SUMS`, `verify_package.py`.

## Install (root)

```bash
PY=/opt/python3.13/bin/python3.13                       # the dedicated Python {python}, see the guide
sudo mkdir -p /opt/drishti && sudo tar -xzf drishti-{release}-{target}.tar.gz -C /opt/drishti      # one folder per release, never over another
cd /opt/drishti/drishti-{release}-{target}
$PY verify_package.py                                   # every file against SHA256SUMS: "package verified"
sudo $PY -m pip install --no-index --find-links wheels -r wheels/requirements.txt
sudo $PY -m pip install --no-index --find-links wheels -r wheels/python.lock
sudo $PY drishti/tools/drishti.py setup --settings /etc/drishti/prod.ini     # checks everything: "Drishti is ready."
sudo chown -R root:root . && sudo chmod -R go-w .
```

Then the settings and secrets of the guide (sections 4 to 6), the units from `drishti/deploy/systemd/prod/`, and `systemctl enable --now`.

## Upgrade and rollback

Unpack the new package beside the old one, run the same checks, carry over `drishti/lib/ext`, stop both services, point `release.env` at
the new folder, start. Rollback is the reverse: the old folder is untouched. The site's settings and data are outside the release.
"""

VERIFY = '''# Verify a Drishti binary package against its SHA256SUMS. Python standard library only.
# Usage: python verify_package.py [package folder]   (default: the folder of this file). Exit 0: "package verified".
import hashlib
import sys
from pathlib import Path

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
sums = root / "SHA256SUMS"
if not sums.is_file():
    sys.exit(f"{sums} not found")
bad, n, listed = [], 0, set()
for line in sums.read_text(encoding="utf-8").splitlines():
    h, _, name = line.partition("  ")
    listed.add(name)
    p = root / name
    n += 1
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != h:
        bad.append(name)
extra = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p.name != "SHA256SUMS"
               and p.relative_to(root).as_posix() not in listed)
if bad or extra:
    for b in bad[:20]:
        print("CHANGED or MISSING:", b)
    for e in extra[:20]:
        print("NOT IN SHA256SUMS:", e)
    sys.exit(f"package NOT verified: {len(bad)} changed or missing, {len(extra)} unlisted")
print(f"package verified: {n} files")
'''


def assemble(release: str, target: str, drishti: Path, wheels: dict[str, bytes], out_dir: Path, refs: dict, cfg: dict | None,
             python: str = PYTHON) -> Path:
    if target not in TARGETS:
        raise BinaryError(f"--target must be one of {TARGETS}: production is Linux")
    if not any(n.endswith(".whl") for n in wheels) or "requirements.txt" not in wheels or "python.lock" not in wheels:
        raise BinaryError("the wheel pack needs .whl files, requirements.txt and python.lock (make_wheels.py makes it)")
    files = collect(drishti)
    for w in wheels:                                                    # the Lake wheel also where the install folder looks for it
        if w.startswith("drishti_lake-") and w.endswith(".whl"):
            files["lib/wheels/" + w] = (wheels[w], 0o644)
    top = f"drishti-{release}-{target}"
    entries: dict[str, tuple[bytes, int]] = {f"drishti/{n}": v for n, v in files.items()}
    entries.update({f"wheels/{n}": (b, 0o644) for n, b in wheels.items()})
    man = manifest(release, target, files, wheels, refs, cfg, drishti, python)
    entries["MANIFEST.json"] = ((json.dumps(man, indent=2, sort_keys=True) + "\n").encode(), 0o644)
    entries["INSTALL.md"] = (INSTALL.format(release=release, target=target, python=python).encode(), 0o644)
    entries["verify_package.py"] = (VERIFY.encode(), 0o755)
    entries["SHA256SUMS"] = ("".join(f"{sha256(b)}  {n}\n" for n, (b, _) in sorted(entries.items())).encode(), 0o644)
    out_dir.mkdir(parents=True, exist_ok=True)
    target_path = out_dir / f"{top}.tar.gz"
    tmp = target_path.with_suffix(".tmp")
    with open(tmp, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=6) as gz, \
            tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for name in [top] + sorted({f"{top}/{p}" for n in entries for p in _parents(n)}):
            info = tarfile.TarInfo(name)
            info.type, info.mode, info.mtime = tarfile.DIRTYPE, 0o755, MTIME
            tar.addfile(info)
        for name, (data, mode) in sorted(entries.items()):
            info = tarfile.TarInfo(f"{top}/{name}")
            info.size, info.mode, info.mtime = len(data), mode, MTIME
            tar.addfile(info, io.BytesIO(data))
    tmp.replace(target_path)
    (out_dir / f"{top}.tar.gz.sha256").write_text(f"{sha256(target_path.read_bytes())}  {target_path.name}\n", encoding="utf-8")
    return target_path


def _parents(name: str) -> list[str]:
    parts = name.split("/")[:-1]
    return ["/".join(parts[:i]) for i in range(1, len(parts) + 1)]


def build_from_tags(cfg: dict, release: str, parent: Path, work: Path, maven_repo: Path, skip_tests: bool) -> Path:
    """Archive each repository at its tag into work/, build them in order (the platform's own build, on the BUILD machine), return work/drishti."""
    import build_all
    refs = pl.refs_for(cfg, release, False)
    for name, ref in refs.items():
        folder = parent / cfg["repos"][name]["repo"]
        if not folder.is_dir():
            raise BinaryError(f"{folder} not found: run clone_all.py first")
        dest = work / cfg["repos"][name]["repo"]
        dest.mkdir(parents=True)
        with tarfile.open(fileobj=io.BytesIO(pl.archive(folder, ref))) as tar:
            tar.extractall(dest, filter="data")
    for name, build_dir, cmd in build_all.plan(cfg, work, skip_tests, maven_repo):
        print(f"== {name}: {' '.join(cmd)}", flush=True)
        if subprocess.run(cmd, cwd=build_dir, env=build_all.maven_env(build_dir)).returncode != 0:
            raise BinaryError(f"the build of {name} failed")
    return work / cfg["repos"]["drishti"]["repo"]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--release", required=True)
    p.add_argument("--target", default="linux-x64", choices=TARGETS)
    p.add_argument("--python", default=PYTHON)
    p.add_argument("--parent", type=Path, default=pl.default_parent())
    p.add_argument("--out", type=Path, default=Path.cwd())
    p.add_argument("--built", type=Path, help="a built Drishti folder to assemble from (skips the tag archive and the Maven build)")
    p.add_argument("--wheels", type=Path, help="the wheel pack (zip or folder) of make_wheels.py; without it the pack is made (needs PyPI)")
    p.add_argument("--maven-repo", type=Path, help="Maven repository of the build (default: a folder beside the work folder; never ~/.m2)")
    p.add_argument("--run-tests", action="store_true", help="run the products' tests in the build (default: the tag was gated; skipped)")
    a = p.parse_args(argv)
    try:
        cfg = pl.load()
        release = pl.resolve_release(cfg, a.release)
        refs = pl.refs_for(cfg, release, False) if release in cfg["releases"] else {}
        with tempfile.TemporaryDirectory(prefix="drishti-binary-") as tmp:
            work = Path(tmp)
            if a.built:
                drishti = a.built.resolve()
            elif release in cfg["releases"]:
                drishti = build_from_tags(cfg, release, a.parent.resolve(), work / "src", (a.maven_repo or work / "m2").resolve(), not a.run_tests)
            else:
                raise BinaryError(f"release '{a.release}' is not in platform.yaml: name a release, or give --built <built drishti folder>")
            if a.wheels:
                wheels = wheel_files(a.wheels.resolve())
            elif refs:
                import make_wheels
                wheels = wheel_files(make_wheels.build_one(cfg, release, a.parent.resolve(), work / "wheels", a.target, a.python))
            else:
                raise BinaryError("give --wheels <wheel pack> (make_wheels.py makes it)")
            target = assemble(release, a.target, drishti, wheels, a.out.resolve(), refs, cfg, a.python)
    except pl.PlatformError as e:
        return pl.fail(e)
    print(f"{target} ({target.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
