<!-- Copyright (c) 2026 Ashutosh Sinha <ajsinha@gmail.com>. All rights reserved. Drishti platform. Proprietary: see LICENSE. -->

# Start here: Drishti on Windows

These steps take a Windows PC from the downloads to Drishti running in your browser. Nothing needs to be typed except one line in
step 4. Each step says what you should see.

## What you need first

Ask your IT team to install these once, if they are not already on the PC:

- **Java 21** (a JDK), for example in `C:\Program Files\Java\jdk-21`, with `JAVA_HOME` set to that folder (or `java` on the PATH).
- **Python 3.13** from python.org, with the **py launcher** (the standard installer includes it). If Python is installed for all
  users under `C:\Program Files`, ask IT to run step 4 for you as an administrator, or use a Python installed just for you.
- **IntelliJ IDEA** and **PyCharm** (the free Community editions are enough).
- Step 3 needs the company network (it fetches the build tools once).

## 1. Download two files

From the release page (<https://github.com/drishti-platform/drishti-platform/releases>, the newest release):

- `drishti-platform-<release>-source.zip`: Drishti and its parts.
- `drishti-platform-<release>-wheels-windows-x64-py313.zip`: the Python libraries Drishti needs, so nothing is fetched from the internet.

## 2. Unzip them

1. Unzip the **source** zip into `C:\Users\<you>\IdeaProjects\drishti-platform\`.
   *You should see* the folders `drishti`, `drishti-lake`, `drishti-rachana`, `drishti-tools`, `drishti-elements`, and the files `pom.xml`
   and this guide.
2. Unzip the **wheels** zip into `C:\Users\<you>\drishti-wheels\`.
   *You should see* many files ending in `.whl` and a `README.txt` directly in that folder.

## 3. Build Drishti (IntelliJ IDEA)

1. Start IntelliJ IDEA. **File → Open**, choose `C:\Users\<you>\IdeaProjects\drishti-platform\pom.xml`, then **Open as Project**.
   If IntelliJ asks whether to trust the project, click **Trust Project**.
2. **File → Project Structure → Project → SDK**: choose the Java 21 folder (**Add SDK → JDK…** if it is not listed). Click **OK**.
3. Wait until the progress bar at the bottom finishes (indexing). Then, at the top right, open the list of run configurations, choose
   **platform-clean-install**, and click the green **Run** arrow.
4. Wait. It takes several minutes the first time.
   *You should see* `BUILD SUCCESS` at the end of the output.

## 4. Prepare Python (one line, once)

1. Open a **Command Prompt** (press the Windows key, type `cmd`, press Enter).
2. Type these two lines (replace `<you>` with your Windows user name):
   ```
   cd C:\Users\<you>\IdeaProjects\drishti-platform\drishti
   py -3.13 tools\drishti.py setup --system --wheels C:\Users\<you>\drishti-wheels
   ```
   *You should see* a list of lines starting with `[  ok]`, the libraries installed from the wheels folder, and at the end **Next steps**.
   No internet is used. If a line says `[FAIL]`, it says what is wrong in plain words.
3. Note the path on the line that starts with `[  ok] python` (for example `C:\Users\<you>\AppData\Local\Programs\Python\Python313\python.exe`):
   PyCharm needs it in step 5.

## 5. Prepare the demo data (PyCharm, once)

1. Start PyCharm. **File → Open**, choose the folder `C:\Users\<you>\IdeaProjects\drishti-platform\drishti`. Click **Trust Project**
   if asked. If PyCharm offers to create a virtual environment, click **Cancel**: Drishti uses the Python from step 4.
2. **Settings → Project → Python Interpreter → Add Interpreter → Add Local Interpreter → System Interpreter**: choose the `python.exe`
   you noted in step 4. Click **OK**, and wait until the progress bar at the bottom finishes.
3. At the top right choose **Drishti: build demo lakes** and click **Run**.
   *You should see* `Demo lake ready` at the end (a few minutes). Only needed the first time.

## 6. Start Drishti

1. **The server (IntelliJ IDEA):** **File → Open**, choose `C:\Users\<you>\IdeaProjects\drishti-platform\drishti\pom.xml`,
   **Open as Project**, and choose **New Window** when asked. Trust the project, pick the same Java 21 as in step 3, and wait for the
   progress bar. Choose **Drishti: run server (demo)** at the top right and click **Run**.
   *You should see* `Started DrishtiApplication` after a minute or so. Leave this window open.
2. **The console (PyCharm):** choose **Drishti: run console** and click **Run**.
   *You should see* `Uvicorn running on http://0.0.0.0:17480`.
3. The first time, Windows may ask whether Java and Python may use the network: click **Allow**.

## 7. Open Drishti

1. In your browser, go to **http://localhost:17480**.
2. Sign in as `drishti-dev-admin` with the password `drishti-dev-admin123`.
3. Type `VAR BANK` in the search box and press **GO**.
   *You should see* the bank's VaR: **167,372,692**, and ES **210,131,972**.

## To stop

Click the red **Stop** square in PyCharm (the console) and in IntelliJ IDEA (the server).

## If something goes wrong

Take a photo or screenshot of the whole window and send it to your Drishti contact. The step number above helps. More detail for
technical readers: `IDE_GUIDE.md` (beside this file) and `drishti\docs\guides\IDE_GUIDE.md`.
