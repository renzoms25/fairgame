# -*- mode: python ; coding: utf-8 -*-
# Builds FairGame for the current OS.  Use packaging/build.py rather than running this directly.
#
# Produces two programs from app.py sharing one set of libraries:
#   FairGame         the window (no console)
#   fairgame-engine  the console bot, which the window runs in the background
# On macOS both go inside FairGame.app.
import os
import sys

from PyInstaller.utils.hooks import collect_all

sys.path.insert(0, SPECPATH)
from common.paths import BUNDLED_RESOURCES

datas = [(resource, os.path.dirname(resource) or ".") for resource in BUNDLED_RESOURCES]
binaries, hiddenimports = [], []
# selenium ships its selenium-manager binary as package data, apprise loads its notification
# plugins dynamically, amazoncaptcha needs its training data and customtkinter its themes
for package in ["selenium", "apprise", "amazoncaptcha", "customtkinter"]:
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

a = Analysis(
    ["app.py"],
    datas=datas,
    binaries=binaries,
    hiddenimports=hiddenimports,
    excludes=["tests", "pytest"],
)
pyz = PYZ(a.pure)
gui = EXE(pyz, a.scripts, [], exclude_binaries=True, name="FairGame", console=False, upx=False)
engine = EXE(pyz, a.scripts, [], exclude_binaries=True, name="fairgame-engine", console=True, upx=False)
coll = COLLECT(gui, engine, a.binaries, a.datas, name="FairGame", upx=False)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="FairGame.app",
        bundle_identifier="io.github.renzoms25.fairgame",
        info_plist={"NSHighResolutionCapable": True},
    )
