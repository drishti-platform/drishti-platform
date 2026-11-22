# Copyright (c) 2026 Ashutosh Sinha <ajsinha@gmail.com>. All rights reserved.
# Drishti platform. Proprietary: see LICENSE.
"""Build drishti-platform-<release>-source.zip: each repository's source at its tag (git archive), README.md, build_all.py,
platform_lib.py, platform.yaml, COMPATIBILITY.md and SHA-256SUMS.

python make_bundle.py --release i7b [--parent <folder>] [--out <folder>]
Needs the repositories cloned in the parent folder (clone_all.py). A branch ref (main) is archived at its current commit.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import platform_lib as pl

TOP_FILES = ["README.md", "COMPATIBILITY.md", "platform.yaml", "platform_lib.py", "build_all.py", "LICENSE"]


def archive(folder: Path, ref: str) -> bytes:
    check = subprocess.run(["git", "rev-parse", "--verify", "--quiet", ref + "^{commit}"], cwd=folder, capture_output=True)
    if check.returncode != 0:
        raise pl.PlatformError(f"{folder.name}: '{ref}' does not exist yet")
    out = subprocess.run(["git", "archive", "--format=tar", ref], cwd=folder, capture_output=True)
    if out.returncode != 0:
        raise pl.PlatformError(f"git archive failed in {folder}: {out.stderr.decode(errors='replace')}")
    return out.stdout


def build(cfg: dict, release: str, parent: Path, out_dir: Path) -> Path:
    refs = pl.refs_for(cfg, release, False)
    target = out_dir / f"drishti-platform-{release}-source.zip"
    sums: list[tuple[str, str]] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        def put(name: str, data: bytes, mode: int = 0o644) -> None:
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.external_attr = (mode & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
            sums.append((hashlib.sha256(data).hexdigest(), name))

        for name, ref in refs.items():
            folder = parent / cfg["repos"][name]["repo"]
            if not folder.is_dir():
                raise pl.PlatformError(f"{folder} not found: run clone_all.py first")
            prefix = cfg["repos"][name]["repo"] + "/"
            with tarfile.open(fileobj=io.BytesIO(archive(folder, ref))) as tar:
                for m in tar.getmembers():
                    if not m.isfile():
                        continue
                    put(prefix + m.name, tar.extractfile(m).read(), m.mode)
        for f in TOP_FILES:
            put(f, (pl.HERE / f).read_bytes())
        z.writestr("SHA-256SUMS", "".join(f"{h}  {n}\n" for h, n in sorted(sums, key=lambda s: s[1])))
    return target


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--release", required=True)
    p.add_argument("--parent", type=Path, default=pl.default_parent())
    p.add_argument("--out", type=Path, default=Path.cwd())
    a = p.parse_args(argv)
    try:
        target = build(pl.load(), a.release, a.parent.resolve(), a.out.resolve())
    except pl.PlatformError as e:
        return pl.fail(e)
    print(f"{target} ({target.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
