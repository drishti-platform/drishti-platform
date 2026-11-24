<!-- Copyright (c) 2026 Ashutosh Sinha <ajsinha@gmail.com>. All rights reserved. Drishti platform. Proprietary: see LICENSE. -->

# The Drishti platform in your IDE

**New to Drishti on Windows?** `START_HERE_WINDOWS.md` (and its PDF) beside this guide has the same path in plain words.

From the release zip to a running Drishti server and console, with nothing to edit by hand. IntelliJ IDEA builds and runs the
server (Java only); PyCharm runs the console (Python). Windows is shown; Linux and macOS are the same with `/` paths and `python3`.

**You need:** a JDK 21 (for example `C:\jdk-21`), Python 3.10 or later (`py`), IntelliJ IDEA (Community or Ultimate) and PyCharm. No
`.exe` is added to the machine.

## 1. Get the release

Download **`drishti-platform-<release>-source.zip`** from
[the releases of the index repository](https://github.com/drishti-platform/drishti-platform/releases) (its SHA-256 is in the release notes)
and unzip it to `C:\Users\<you>\IdeaProjects\drishti-platform\`:

```
drishti-platform\
    pom.xml                 the platform pom: builds tools, Rachana, Lake, Drishti in that order
    .idea\runConfigurations\  its IntelliJ launchers (group Drishti-platform 1 Build: platform-clean-install)
    IDE_GUIDE.md            this guide
    drishti\  drishti-tools\  drishti-rachana\  drishti-lake\  drishti-elements\
                            each product at its release tag; drishti\lib\wheels\ already holds the pinned Lake Python wheel
```

With git you can instead run `py clone_all.py --release <release> --parent C:\Users\<you>\IdeaProjects\drishti-platform` from the index
repository: it clones the same set and puts `pom.xml`, `.idea\runConfigurations\` and this guide beside it (the Lake wheel is then built once, as
`drishti\lib\lake-wheel.pin` says).

## 2. Build everything (IntelliJ, window 1)

1. **File, Open**: the top `pom.xml`, **Open as Project**.
2. **File, Project Structure, Project, SDK**: the JDK 21. **Settings, Build Tools, Maven, Runner, JRE**: *Use Project JDK*.
3. The run-configuration drop-down (top right): **`platform-clean-install`** (Linux and macOS: **`platform-clean-install (Linux, macOS)`**),
   then **Run**.

It runs a **clean install** of the four Java products in order, **without tests**. On Windows it trusts the **Windows certificate store**,
both in IntelliJ's own Maven (the launcher's VM option) and in the four product builds (the pom's Windows profile), so a company proxy's
root certificate is accepted with nothing else to set.

*You should see* `BUILD SUCCESS` five times (the four products and the platform), the server jar in `drishti\lib\` and twelve `.dmod`
packages in `drishti\modules\`.

**The launcher is not in the drop-down?** **Settings, Build Tools, Maven, Runner**: **VM Options** `-Djavax.net.ssl.trustStoreType=Windows-ROOT`
and tick **Skip Tests**; then the **Maven** tool window, **drishti-platform, Lifecycle, validate**. From a terminal in the same folder:
`mvn -DskipTests` (the pom passes the Windows option itself; the terminal's own Maven may need `set MAVEN_OPTS=-Djavax.net.ssl.trustStoreType=Windows-ROOT`
first).

This project only builds. To read and change a product's code, open that product as its own project (section 4).

## 3. Run Drishti

1. **Prepare once (a terminal):**
   ```
   cd C:\Users\<you>\IdeaProjects\drishti-platform\drishti
   py tools\drishti.py setup
   ```
   It makes the settings file `%USERPROFILE%\drishti-envs\dev.ini`, the JVM argument files and the console's Python
   (`drishti-console\.venv`), and prints the next steps. An older `dev.ini` or JVM argument file from another copy of Drishti is
   moved into a dated folder, `%USERPROFILE%\drishti-envs\replaced-<date>\`, and a fresh one written: nothing is lost and nothing
   is left to rename by hand. Setup never creates a folder outside this checkout.
2. **Server, IntelliJ (window 2):** **File, Open** `drishti\pom.xml`, **Open as Project**, the same JDK 21. Run **Drishti: run server (demo)**.
   *You should see* `Started DrishtiApplication`.
3. **Console, PyCharm:** **File, Open** the `drishti` folder. **Settings, Project, Python Interpreter, Add Interpreter, Existing**:
   `drishti\drishti-console\.venv\Scripts\python.exe`. Run **Drishti: build demo lakes** once, with no server running; then **Drishti console**.
   *You should see* `Uvicorn running on http://0.0.0.0:17480`.
4. **Check:** open `http://localhost:17480`, sign in as `drishti-dev-admin` / `drishti-dev-admin123`, type `VAR BANK` and press **GO**.

**No virtual environment: the system Python.** Where a machine allows no `.venv` (everything goes to the Python the company
provides), one command prepares it, standard library only to start with:

1. `py tools\drishti.py setup --system --wheels C:\Users\<you>\drishti-wheels` with the release's offline wheel pack unzipped there (no package index, no internet; without `--wheels` pip uses your package index), or in PyCharm the launcher **Drishti: setup (system Python, offline wheels)** (it reads `%USERPROFILE%\drishti-wheels`): it prepares Drishti (step 1) and
   installs the console's libraries into that Python, the pinned Lake wheel from `lib\wheels\` first, then
   `drishti-console\requirements.txt`, through the Windows certificate store; it writes `drishti.python` (that Python's full path) into
   `dev.ini`.
2. PyCharm: **Settings, Project, Python Interpreter, Add Interpreter, System Interpreter**: the same `python.exe`.
3. Nothing to set for the server: it reads `drishti.python` from `dev.ini` for its Python work (`DRISHTI_PYTHON` only overrides it).
4. Check: `py tools\drishti.py setup --check --system` lists every library and says what, if anything, is missing.

Drishti's own IDE guide (`drishti\docs\guides\IDE_GUIDE.md`) has every launcher, the settings file, a step-by-step check of each step
(section 8) and the troubleshooting recipes (section 6). The deployment and QA guide (`drishti\docs\DEPLOYMENT_AND_QA_GUIDE.md`) covers
running it as a service and the QA checklist.

## 4. Work on a product's code

Open each product as its own project, with its own launchers in its `.idea\runConfigurations\` (groups Drishti-java 2 Run for Drishti's IntelliJ launchers; Drishti-python 1 Setup, 2 Data, 3 Run, 4 Check for the console's PyCharm launchers):

| Product | IntelliJ: open | PyCharm: open | Its guide |
|---|---|---|---|
| Drishti | `drishti\pom.xml` | `drishti\` | `drishti\docs\guides\IDE_GUIDE.md` |
| Drishti Rachana | `drishti-rachana\java\pom.xml` | `drishti-rachana\python\` | `drishti-rachana\README.md` |
| Drishti Lake | `drishti-lake\java\pom.xml` | `drishti-lake\python\` | `drishti-lake\README.md` |
| Drishti Tools | `drishti-tools\java\pom.xml` | — | `drishti-tools\README.md` |
| Drishti Elements | — (JavaScript) | — | `drishti-elements\README.md` |

The products build and install in the order tools, Rachana, Lake, then Drishti; Drishti reads the other three from `~/.m2`, which
`platform-clean-install` fills from the release tags.
