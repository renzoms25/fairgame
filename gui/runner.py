#      FairGame - Automated Purchasing Program
#      Copyright (C) 2021  Hari Nagarajan
#
#      This program is free software: you can redistribute it and/or modify
#      it under the terms of the GNU General Public License as published by
#      the Free Software Foundation, either version 3 of the License, or
#      (at your option) any later version.
#
#      This program is distributed in the hope that it will be useful,
#      but WITHOUT ANY WARRANTY; without even the implied warranty of
#      MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#      GNU General Public License for more details.
#
#      You should have received a copy of the GNU General Public License
#      along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
#      The author may be contacted through the project's GitHub, at:
#      https://github.com/Hari-Nagarajan/fairgame

"""Runs the command line bot as a background process and streams its output"""

import os
import subprocess
import sys
import threading

import psutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def engine_command():
    if getattr(sys, "frozen", False):
        # Console build of the same program, shipped next to the GUI executable (see fairgame.spec)
        name = "fairgame-engine.exe" if sys.platform == "win32" else "fairgame-engine"
        return [os.path.join(os.path.dirname(sys.executable), name)]
    return [sys.executable, os.path.join(ROOT, "app.py")]


class BotProcess:
    def __init__(self, on_line, on_exit):
        """Both callbacks are called from a background thread"""
        self.on_line = on_line
        self.on_exit = on_exit
        self.process = None
        self.stopping = False

    @property
    def running(self):
        return self.process is not None and self.process.poll() is None

    def start(self, args, password):
        env = dict(os.environ)
        env["FAIRGAME_PASSWORD"] = password
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        self.stopping = False
        self.process = subprocess.Popen(
            engine_command() + args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        threading.Thread(target=self._pump, args=(self.process,), daemon=True).start()

    def _pump(self, process):
        for raw in iter(process.stdout.readline, b""):
            self.on_line(raw.decode("utf-8", errors="replace").rstrip())
        self.on_exit(process.wait(), self.stopping)

    def stop(self):
        """Kills the bot along with the chromedriver and Chrome processes it started"""
        if not self.running:
            return
        self.stopping = True
        try:
            parent = psutil.Process(self.process.pid)
            processes = parent.children(recursive=True) + [parent]
        except psutil.NoSuchProcess:
            return
        for process in processes:
            try:
                process.kill()
            except psutil.NoSuchProcess:
                pass
        psutil.wait_procs(processes, timeout=5)
