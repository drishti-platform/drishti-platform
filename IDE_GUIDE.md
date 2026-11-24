<!-- Copyright (c) 2026 Ashutosh Sinha <ajsinha@gmail.com>. All rights reserved. Drishti platform. Proprietary: see LICENSE. -->

# The Drishti platform in your IDE

**New to Drishti?** `START_HERE_WINDOWS.pdf` (or `_LINUX`, `_MACOS`) beside this guide has the same path in numbered plain steps. This
guide is the reference behind it: which IDE opens what, every launcher group, the command line that does the same, and what to do when
something stops. Windows is shown; Linux and macOS are the same with `/` paths and `python3.13` instead of `py -3.13`.

**You need:** a JDK 21 (for example `C:\Program Files\Java\jdk-21`), Python 3.13 with the `py` launcher, IntelliJ IDEA and PyCharm
(Community editions are enough), the release's source zip and its wheel pack for your computer, and at least 20 GB free on the disk.
Drishti never creates a Python environment and never installs packages: you install them once (section 3), setup only checks.

## 1. Which IDE opens what

| You open | In | You see these launcher groups |
|---|---|---|
| `drishti-platform\pom.xml` | IntelliJ IDEA | **IntelliJ-platform-build** (`platform-clean-install`), and the products' groups below |
| `drishti-platform\drishti\pom.xml` | IntelliJ IDEA | **IntelliJ-drishti-build**, **IntelliJ-drishti-run**, **IntelliJ-drishti-test** |
| `drishti-platform\drishti\drishti-console` | PyCharm | **PyCharm-console-setup**, **PyCharm-console-data**, **PyCharm-console-run**, **PyCharm-console-check** |
| `drishti-tools\java\pom.xml` | IntelliJ IDEA | **IntelliJ-tools-build / -test / -check / -install** |
| `drishti-rachana\java\pom.xml` (Python: `drishti-rachana\python`) | IntelliJ IDEA (PyCharm) | **IntelliJ-rachana-build / -run / -test / -check / -install** (**PyCharm-rachana-run / -test / -check**) |
| `drishti-lake\java\pom.xml` (Python: `drishti-lake\python`) | IntelliJ IDEA (PyCharm) | **IntelliJ-lake-build / -run / -test / -check / -install** (**PyCharm-lake-test / -check**) |
| `drishti-elements` | IntelliJ IDEA / PyCharm | **IntelliJ-elements-run / -test**, **PyCharm-elements-build / -test / -check** |

Every group is named **IDE-part-purpose**. The launchers live in ordinary `run-configs\` folders (`*.run.xml`), which both IDEs read
from anywhere inside the project they open, so a project that contains another (the platform contains them all) also lists the inner
ones. IntelliJ IDEA may list PyCharm groups, under **Unknown** when it has no Python plugin: they are for PyCharm, ignore them there.

## 2. Build everything (IntelliJ IDEA)

1. **File → Open** the top `pom.xml`, **Open as Project**, **Trust Project**.
2. **File → Project Structure → Project → SDK**: the JDK 21.
3. Group **IntelliJ-platform-build** → **platform-clean-install** (Linux and macOS: **platform-clean-install (Linux, macOS)**) → **Run**.
   *You should see* `BUILD SUCCESS`; the server jar in `drishti\lib\` and twelve `.dmod` packages in `drishti\modules\`.

It builds and installs tools, Rachana, Lake and Drishti in that order, tests skipped; on Windows it trusts the Windows certificate store
(a company proxy's root is accepted) and runs Rachana's small Python step with `py`. **Command line, same result:**
`py -3.13 build_all.py --skip-tests` in `drishti-platform`.

## 3. Prepare Python (once, a Command Prompt)

```
cd "C:\Users\<you>\IdeaProjects\drishti-platform\drishti\drishti-console"
py -3.13 -m pip install --no-index --find-links "C:\Users\<you>\drishti-wheels" -r requirements.txt
py -3.13 -m pip install --no-index --find-links "C:\Users\<you>\drishti-wheels" -r ..\config\compute\locks\python.lock
cd ..
py -3.13 tools\drishti.py setup
```

The wheel pack must be **unzipped** in `drishti-wheels`. A Python under `C:\Program Files` needs the Command Prompt **as administrator**
(or `--user` on both pip lines). The second line sets exact pandas, pyarrow and tzdata versions in that Python: if other work shares it,
use a second Python 3.13 just for Drishti. Setup ends with **Drishti is ready.**; it writes your settings file
`%USERPROFILE%\drishti-envs\dev.ini` (an older one from another copy is moved to `drishti-envs\replaced-<date>\`) and the JVM files the
server launchers use. In PyCharm, **PyCharm-console-setup → Drishti: setup** runs the same check.

## 4. Run Drishti from the IDEs

1. **PyCharm:** **File → Open** `drishti\drishti-console`. If it offers to create an environment, **Cancel**. **Settings → Project →
   Python Interpreter → Add Interpreter → Add Local Interpreter → System Interpreter**: the `python.exe` setup named on its
   `drishti.python` line. Then **PyCharm-console-data → Drishti: build demo lakes** (first time only).
2. **IntelliJ IDEA:** **File → Open** `drishti\pom.xml`, **Open as Project**, **New Window**, the same JDK 21. **IntelliJ-drishti-run →
   Drishti: run server (demo)**. *You should see* `Started DrishtiApplication`.
3. **PyCharm:** **PyCharm-console-run → Drishti: run console**. *You should see* `Uvicorn running on http://0.0.0.0:17480`.
4. Browser: `http://localhost:17480`, sign in as `drishti-dev-admin` / `drishti-dev-admin123`, `VAR BANK` → **167,372,692**
   (ES **210,131,972**). Or **PyCharm-console-check → acceptance**: one PASS line with both figures.

## 5. The same from the command line

Every launcher is a command; Drishti can show and run them from the launcher files themselves (in `drishti`):

| Do | Command |
|---|---|
| list every launcher, its group and its exact command | `py -3.13 tools\drishti.py launchers --list` |
| run a launcher by name (or a unique start of it) | `py -3.13 tools\drishti.py launchers --run "Drishti: run server (demo)"` |
| a launcher that asks for a value in the IDE | `py -3.13 tools\drishti.py launchers --run "Drishti: run loader" --input C:\data\trades.jsonl` |
| demo lakes | `py -3.13 tools\drishti.py lake demo --engine java` |
| server and console together | `py -3.13 tools\drishti.py start all --demo` |
| what runs / stop | `py -3.13 tools\drishti.py status` / `py -3.13 tools\drishti.py stop all` |
| check everything | `py -3.13 tools\drishti.py doctor --acceptance` (PASS with VaR and ES) |

## 6. When something stops

| You see | Means | Do |
|---|---|---|
| a launcher missing, or red | the IDE opened another folder | open the folder of section 1 for that group |
| IntelliJ: **module not specified** on a Lake/Rachana Application launcher | you opened the platform, not that product | open that product's own `java\pom.xml` |
| PyCharm: **No Python interpreter** | step 4.1 not done | choose the Python setup named |
| setup `[FAIL] libraries …` | section 3's pip lines not run in this Python | run them, then setup again |
| setup `[FAIL] wheel pack … still zipped` | the pack is still a zip | unzip it into `drishti-wheels` |
| setup lists **build all** | the server is not built | section 2, then setup again |
| `port 18480 (or 17480) is in use` | Drishti (or something else) already runs | `py -3.13 tools\drishti.py stop all`, or another `--port` |
| VaR: *not enough free disk* | under 20 GB free | free space, or `drishti.disk.min-free-gb=10` in `dev.ini` |

Every `[FAIL]` line ends with `Fix:` and the command to run. Drishti's own guide, `drishti\docs\guides\IDE_GUIDE.md`, has every launcher
in detail; running Drishti for real users on a Linux server: `drishti\docs\PRODUCTION_DEPLOYMENT.md`.
