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

"""GUI state and translation to bot command line arguments.  Nothing here touches Tk."""

import json
import os
import re

GUI_SETTINGS_PATH = "config/gui_settings.json"

AMAZON_SITES = [
    "www.amazon.com",
    "www.amazon.ca",
    "www.amazon.co.uk",
    "www.amazon.de",
    "www.amazon.fr",
    "www.amazon.it",
    "www.amazon.es",
    "www.amazon.nl",
    "www.amazon.pl",
    "www.amazon.se",
    "www.amazon.com.tr",
    "www.amazon.co.jp",
    "www.amazon.sg",
]

DEFAULT_OPTIONS = {
    "test": True,
    "delay": 3.0,
    "single_shot": False,
    "used": False,
    "checkshipping": False,
    "sounds": True,
    "headless": False,
    "no_image": False,
    "slow_mode": False,
    "captcha_wait": False,
    "detailed": False,
    "log_stock_check": True,
    "shipping_bypass": False,
    "discord": False,
}

# option -> flag passed to `app.py amazon` when the option is True
TRUE_FLAGS = {
    "test": "--test",
    "single_shot": "--single-shot",
    "used": "--used",
    "checkshipping": "--checkshipping",
    "headless": "--headless",
    "no_image": "--no-image",
    "slow_mode": "--slow-mode",
    "captcha_wait": "--captcha-wait",
    "detailed": "--detailed",
    "log_stock_check": "--log-stock-check",
    "shipping_bypass": "--shipping-bypass",
}
# option -> flag passed when the option is False
FALSE_FLAGS = {
    "sounds": "--disable-sound",
    "discord": "--disable-presence",
}


def build_bot_args(options):
    args = ["amazon"]
    for option, flag in TRUE_FLAGS.items():
        if options.get(option, DEFAULT_OPTIONS[option]):
            args.append(flag)
    for option, flag in FALSE_FLAGS.items():
        if not options.get(option, DEFAULT_OPTIONS[option]):
            args.append(flag)
    args += ["--delay", f"{float(options.get('delay', DEFAULT_OPTIONS['delay'])):g}"]
    return args


def parse_price_input(text):
    """'$1,299.99' -> 1299.99, '1.000,50 €' -> 1000.5.  Raises ValueError"""
    cleaned = re.sub(r"[^\d.,]", "", text)
    if re.search(r",\d{1,2}$", cleaned) and cleaned.rfind(",") > cleaned.rfind("."):
        # Decimal comma, with optional dots as thousands separators
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(",", "")
    if not cleaned:
        raise ValueError(f"'{text}' is not a price")
    return float(cleaned)


def load_options(path=GUI_SETTINGS_PATH):
    options = dict(DEFAULT_OPTIONS)
    try:
        with open(path, encoding="utf-8") as f:
            saved = json.load(f)
        options.update({k: v for k, v in saved.items() if k in DEFAULT_OPTIONS})
    except (OSError, ValueError):
        pass
    return options


def save_options(options, path=GUI_SETTINGS_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(options, f, indent=2)


def items_from_config(config):
    """Inverse of cli.setup_wizard.build_config: returns (website, [(asins, min, max), ...])"""
    groups = []
    for idx in range(1, int(config.get("asin_groups", 0)) + 1):
        groups.append(
            (
                list(config.get(f"asin_list_{idx}", [])),
                float(config.get(f"reserve_min_{idx}", 0)),
                float(config.get(f"reserve_max_{idx}", 0)),
            )
        )
    return config.get("amazon_website", AMAZON_SITES[0]), groups


# First matching fragment in a bot log line -> status shown in the window
STATUS_PATTERNS = [
    ("Waiting for home page", "Opening Amazon…"),
    (
        "item(s) in your cart",
        "Your Amazon cart isn't empty. Empty it, then press Start.",
    ),
    ("Lets log in", "Signing in to Amazon…"),
    ("One Time Password", "Enter the code Amazon sent you in the Chrome window"),
    ("two-step verification", "Enter the code Amazon sent you in the Chrome window"),
    ("Incorrect Password", "Wrong FairGame password"),
    ("Checking stock for items", "Watching for stock"),
    ("Adding to cart", "In stock! Checking out…"),
    ("but this is a test", "Test complete: reached checkout without buying ✓"),
    ("Order Placed", "Order placed! Check your Amazon orders"),
    ("maybe this worked", "Order probably placed! Check your Amazon orders"),
    ("maybe this didn't work", "Checkout unclear. Check your Amazon orders"),
    ("FairGame bot ran for", "Finished"),
]


def status_for_line(line):
    for fragment, status in STATUS_PATTERNS:
        if fragment in line:
            return status
    return None


LOG_LINE = re.compile(r"^\d{4}-\d\d-\d\d (\d\d:\d\d:\d\d)[^|]*\|[^|]*\|(\w+)\|(.*)$")


def format_log_line(line):
    """'2026-10-17 15:39:35,123|0.7.0|INFO|Checking stock' -> ('15:39:35  Checking stock', 'INFO')"""
    match = LOG_LINE.match(line)
    if not match:
        return line, None
    time, level, message = match.groups()
    return f"{time}  {message}", level
