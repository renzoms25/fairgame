# -*- mode: python ; coding: utf-8 -*-
# Builds a single FairGame executable for the current OS.  Use packaging/build.py rather than
# running this directly, since the executable also needs the files that build.py puts next to it.
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []
# selenium ships its selenium-manager binary as package data, apprise loads its notification
# plugins dynamically and amazoncaptcha needs its training data
for package in ["selenium", "apprise", "amazoncaptcha"]:
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
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="FairGame",
    console=True,
    upx=False,
)
