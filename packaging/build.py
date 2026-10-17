"""Builds a ready to share FairGame zip for the current OS.

    pipenv run python packaging/build.py

Output: dist/FairGame-<os>.zip containing the app and READ ME FIRST.txt
"""

import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

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
    staging = DIST / f"FairGame-{os_name}"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir()
    shutil.copy2(
        ROOT / "packaging" / "READ ME FIRST.txt", staging / "READ ME FIRST.txt"
    )

    archive = DIST / f"FairGame-{os_name}.zip"
    archive.unlink(missing_ok=True)
    if os_name == "mac":
        # The .app contains symlinks and a code signature that a plain zip would break
        shutil.copytree(DIST / "FairGame.app", staging / "FairGame.app", symlinks=True)
        subprocess.run(
            ["ditto", "-c", "-k", "--keepParent", str(staging), str(archive)],
            check=True,
        )
    else:
        shutil.copytree(DIST / "FairGame", staging / "FairGame", symlinks=True)
        shutil.make_archive(str(archive.with_suffix("")), "zip", DIST, staging.name)
    print(f"Built {archive}")


if __name__ == "__main__":
    main()
