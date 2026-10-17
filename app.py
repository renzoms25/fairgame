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
import os
import sys
import hashlib
import atexit
from common.license_hash import license_hash

# True when running as a packaged executable (see fairgame.spec)
FROZEN = getattr(sys, "frozen", False)

if FROZEN:
    # A double-clicked executable starts in an arbitrary directory, but LICENSE, config/,
    # logs/ etc. all live next to it
    os.chdir(os.path.dirname(sys.executable))

    # Keep the console window open so messages (and errors) can be read before it closes
    def pause_before_closing():
        try:
            input("\nPress Enter to close this window...")
        except (EOFError, KeyboardInterrupt):
            pass

    atexit.register(pause_before_closing)


def sha256sum(filename):
    h = hashlib.sha256()
    b = bytearray(128 * 1024)
    mv = memoryview(b)
    with open(filename, "rb", buffering=0) as f:
        for n in iter(lambda: f.readinto(mv), 0):
            h.update(mv[:n])
    return h.hexdigest()


if os.path.exists("LICENSE") and sha256sum("LICENSE") in license_hash:
    s = """
    FairGame Copyright (C) 2021 Hari Nagarajan
        This program comes with ABSOLUTELY NO WARRANTY; for details
        start the program with the `show --w' option.

        This is free software, and you are welcome to redistribute it
        under certain conditions; for details start the program with
        the `show --c' option.\n
    """

    print(s)
else:
    print("License File Changed or Missing. Quitting Program.")
    sys.exit(0)


def notfound_message(exception):
    print(exception)
    print(
        f"Missing '{exception.name}' module.  If you ran 'pipenv install', try 'pipenv install {exception.name}'"
    )
    print("Exiting...")


try:
    from cli import cli
except ModuleNotFoundError as e:
    notfound_message(e)
    sys.exit(0)


def launch_interactive():
    """What happens when someone double-clicks the executable instead of using the command line"""
    import click
    from cli.setup_wizard import AUTOBUY_CONFIG_PATH, run_setup_wizard

    if not os.path.exists(AUTOBUY_CONFIG_PATH):
        run_setup_wizard()
    elif click.confirm("\nChange which items FairGame is watching?", default=False):
        run_setup_wizard()

    test = click.confirm(
        "\nDo a TEST run? (goes all the way to checkout but does NOT buy anything)",
        default=True,
    )
    cli.main(args=["amazon"] + (["--test"] if test else []))


if __name__ == "__main__":
    try:
        if FROZEN and len(sys.argv) == 1:
            launch_interactive()
        else:
            cli.main()
    except ModuleNotFoundError as e:
        notfound_message(e)
        sys.exit(0)
