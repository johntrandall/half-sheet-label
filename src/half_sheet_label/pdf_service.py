"""Install / remove the macOS PDF Service (⌘P → PDF ▾ → Half-Sheet Label).

Modern macOS won't run a bare script as a PDF Service — it needs a real app
bundle — so we compile a tiny AppleScript app whose `on open` handler runs the
half-sheet-label CLI on the PDF the print system hands it. The app is
version-neutral: it execs whatever `half-sheet-label` is on the resolved PATH,
so brew upgrades don't require reinstalling it.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

APP_NAME = "Half-Sheet Label.app"
SERVICE_DIR = Path.home() / "Library" / "PDF Services"
_LSREGISTER = ("/System/Library/Frameworks/CoreServices.framework/Frameworks/"
               "LaunchServices.framework/Support/lsregister")

# %BIN% is replaced with the absolute half-sheet-label path at install time.
_APPLESCRIPT = """on open theFiles
\tset logf to (POSIX path of (path to home folder)) & "Library/Logs/half-sheet-label-pdfservice.log"
\trepeat with f in theFiles
\t\tset p to POSIX path of f
\t\ttry
\t\t\tset out to do shell script "%BIN% " & quoted form of p
\t\t\tdo shell script "echo " & quoted form of out & " >> " & quoted form of logf
\t\t\tdisplay notification "Label sent to the printer" with title "Half-Sheet Label"
\t\ton error errMsg number errNum
\t\t\tdo shell script "echo " & quoted form of ("ERROR " & errNum & ": " & errMsg) & " >> " & quoted form of logf
\t\t\tdisplay alert "Half-Sheet Label — not printed" message errMsg as warning
\t\tend try
\tend repeat
end open
"""


def _bin_path() -> str:
    return shutil.which("half-sheet-label") or "/opt/homebrew/bin/half-sheet-label"


def install() -> Path:
    """Compile + install the PDF Service app; return its path."""
    if not shutil.which("osacompile"):
        raise RuntimeError("osacompile not found — the PDF Service is macOS-only")
    SERVICE_DIR.mkdir(parents=True, exist_ok=True)
    app = SERVICE_DIR / APP_NAME
    src = Path(tempfile.mkdtemp()) / "half-sheet-label-service.applescript"
    src.write_text(_APPLESCRIPT.replace("%BIN%", _bin_path()))
    if app.exists():
        shutil.rmtree(app)
    subprocess.run(["osacompile", "-o", str(app), str(src)], check=True, capture_output=True)
    # ad-hoc sign so Gatekeeper doesn't flag the unsigned bundle
    subprocess.run(["codesign", "--force", "--deep", "-s", "-", str(app)],
                   check=False, capture_output=True)
    # nudge LaunchServices so it appears in the PDF menu without a re-login
    subprocess.run([_LSREGISTER, "-f", str(app)], check=False, capture_output=True)
    return app


def uninstall() -> bool:
    """Remove the PDF Service app; return True if it existed."""
    app = SERVICE_DIR / APP_NAME
    if app.exists():
        shutil.rmtree(app)
        return True
    return False
