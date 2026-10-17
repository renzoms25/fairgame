"""Builds a ready to share FairGame folder and zip for the current OS.

    pipenv run python packaging/build.py

Output: dist/FairGame-<os>/ and dist/FairGame-<os>.zip
"""

import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Read at runtime relative to the executable's folder, and meant to stay user editable
FILES_NEXT_TO_EXECUTABLE = [
    "LICENSE",
    "config/fairgame.conf",
    "config/amazon_config.template_json",
    "config/apprise.conf_template",
    "notifications/notify.mp3",
    "notifications/purchase.mp3",
    "notifications/alarm-frenzy-493.mp3",
    "cli/license/show_c.txt",
    "cli/license/show_w.txt",
]

OS_NAMES = {"Windows": "windows", "Darwin": "mac", "Linux": "linux"}


def main():
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "fairgame.spec",
        ],
        cwd=ROOT,
        check=True,
    )

    os_name = OS_NAMES[platform.system()]
    executable = "FairGame.exe" if os_name == "windows" else "FairGame"
    out = ROOT / "dist" / f"FairGame-{os_name}"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir()

    shutil.copy2(ROOT / "dist" / executable, out / executable)
    for file in FILES_NEXT_TO_EXECUTABLE:
        destination = out / file
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / file, destination)
    shutil.copy2(ROOT / "packaging" / "READ ME FIRST.txt", out / "READ ME FIRST.txt")

    archive = shutil.make_archive(str(out), "zip", out.parent, out.name)
    print(f"Built {archive}")


if __name__ == "__main__":
    main()
