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

"""File locations.  All paths are relative to the working directory, which is the repository
when running from source and the per-user data directory when running a packaged build.
"""

import os
import shutil
import sys

AMAZON_CONFIG_PATH = "config/amazon_config.json"
AMAZON_CREDENTIAL_FILE = "config/amazon_credentials.json"

# Program files that packaged builds carry inside the executable and copy into the data
# directory on every start, so updates replace them.  User files are never touched.
BUNDLED_RESOURCES = [
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


def user_data_dir():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "FairGame")


def prepare_data_dir():
    """For packaged builds: refresh program files in the data directory and make it the working
    directory.  Apps can't write next to themselves reliably (e.g. macOS runs downloaded apps
    from a read-only location)."""
    data_dir = user_data_dir()
    for resource in BUNDLED_RESOURCES:
        destination = os.path.join(data_dir, resource)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copyfile(os.path.join(sys._MEIPASS, resource), destination)
    os.chdir(data_dir)
    return data_dir
