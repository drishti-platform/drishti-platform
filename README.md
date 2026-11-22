<!-- Copyright (c) 2026 Ashutosh Sinha <ajsinha@gmail.com>. All rights reserved. Drishti platform. Proprietary: see LICENSE. -->
# Drishti platform

The index of the Drishti platform: what the repositories are, which versions go together, and the scripts that fetch and build
them. No product code lives here.

| Repository | What it is |
|---|---|
| **Drishti** | the real-time risk and analytics layer: server, console, packs, engines |
| **Rachana** | the screen grammar (Sutras), compiler and runtimes: describe a screen, supply data, get a UI |
| **Elements** | the reusable JavaScript libraries (grid, charts, inputs, renderer) |
| **Lake** | the storage libraries: Delta and Iceberg readers and writers, loaders |
| **Tools** | shared Java utilities used by the others |

Drishti uses Rachana, Elements and Lake; Rachana and Lake use Tools. Versions that belong together are in
[COMPATIBILITY.md](COMPATIBILITY.md) and [platform.yaml](platform.yaml).

## Install order

Tools, then Rachana, then Lake, then Drishti. Each library repository installs its jars into the Maven repository (`~/.m2`) from its
release tag, and the next one finds them there. `build_all.py` does exactly this.

## Local layout

All repositories sit side by side in one parent folder:

```
~/IdeaProjects/drishti-platform/            (Windows: C:\Users\<you>\IdeaProjects\drishti-platform\)
    drishti-tools/  drishti-rachana/  drishti-lake/  drishti-elements/  drishti/  drishti-platform/ (this index)
```

## Get and build (Python 3.10+, JDK 21; no bash, no .exe)

```
python clone_all.py --release i7b            # clone or update every repository at the release's tags (or --develop)
python build_all.py --release i7b            # build and install in order, then build Drishti
python build_all.py --release i7b --repo-local --skip-tests   # dedicated Maven repository (<parent>/.m2-drishti), no tests
```

`--parent <folder>` changes the parent folder (default: the folder above this repository). Each library is built with its own
`mvnw` / `mvnw.cmd`.

## Source bundle

`python make_bundle.py --release i7b` writes `drishti-platform-i7b-source.zip`: every repository's source at its tag (`git archive`),
this README, `build_all.py` and `SHA-256SUMS`. Unzip, run `python build_all.py --bundle .`, done; it needs no network except Maven
Central.

## Tests

`uv run --with pytest pytest tests` (the logic of the scripts, against a fake repository set).

## Build and run in the IDE

IntelliJ and PyCharm: open the repository root; the launchers are in `run-configs/` (names start with `Platform:`). VS Code: File,
Open Workspace from File, `drishti-platform.code-workspace`.

## Links

Organisation: https://github.com/drishti-platform. Licence: [LICENSE](LICENSE); proprietary, all rights reserved.
