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

"""Interactive replacement for hand editing config/amazon_config.json"""

import json
import re

import click

AUTOBUY_CONFIG_PATH = "config/amazon_config.json"

ASIN_PATTERN = re.compile(r"^[A-Z0-9]{10}$")
# Product links look like https://www.amazon.com/Some-Name/dp/B08HR7SV3M/ref=...
ASIN_IN_URL_PATTERN = re.compile(r"/(?:dp|gp/product|gp/offer-listing)/([A-Z0-9]{10})")


def parse_asins(text):
    """Pull ASINs out of whatever the user pasted: bare ASINs and/or product links,
    separated by commas, spaces or new lines.  Returns (asins, unrecognized)"""
    asins = []
    unrecognized = []
    for token in re.split(r"[\s,]+", text.strip()):
        if not token:
            continue
        match = ASIN_IN_URL_PATTERN.search(token)
        if match:
            asin = match.group(1)
        elif ASIN_PATTERN.match(token.upper()):
            asin = token.upper()
        else:
            unrecognized.append(token)
            continue
        if asin not in asins:
            asins.append(asin)
    return asins, unrecognized


def normalize_website(text):
    """Accepts 'amazon.com', 'https://www.amazon.co.uk/', etc. and returns 'www.amazon.com'"""
    website = re.sub(r"^https?://", "", text.strip().lower()).split("/")[0]
    if website.startswith("smile."):
        website = website[len("smile.") :]
    if not website.startswith("www."):
        website = "www." + website
    return website


def build_config(website, groups):
    """groups is a list of (asins, reserve_min, reserve_max)"""
    config = {"asin_groups": len(groups)}
    for idx, (asins, reserve_min, reserve_max) in enumerate(groups, start=1):
        config[f"asin_list_{idx}"] = asins
        config[f"reserve_min_{idx}"] = reserve_min
        config[f"reserve_max_{idx}"] = reserve_max
    config["amazon_website"] = website
    return config


def prompt_group(number):
    click.echo()
    click.secho(f"--- Item group {number} ---", bold=True)
    click.echo(
        "Paste the Amazon link(s) for the product(s) you want. If you list several,\n"
        "FairGame buys whichever one is in stock first (only one per group)."
    )
    while True:
        asins, unrecognized = parse_asins(click.prompt("Product link(s) or ASIN(s)"))
        if unrecognized:
            click.secho(
                f"Couldn't find a product in: {' '.join(unrecognized)}", fg="red"
            )
        if asins and not unrecognized:
            break
        click.echo("Try again. Copy the link from your browser's address bar.")
    click.echo(f"Found: {', '.join(asins)}")

    click.echo("Prices are before tax. Include shipping only if you use paid shipping.")
    while True:
        reserve_min = click.prompt("Lowest price to buy at", type=click.FloatRange(0))
        reserve_max = click.prompt("Highest price to buy at", type=click.FloatRange(0))
        if reserve_min <= reserve_max:
            break
        click.secho("The lowest price must be less than the highest price.", fg="red")
    return asins, reserve_min, reserve_max


def run_setup_wizard(config_path=AUTOBUY_CONFIG_PATH):
    click.echo()
    click.secho("=== FairGame setup ===", bold=True)
    click.echo("Answer a few questions to choose what FairGame watches for.")
    website = normalize_website(
        click.prompt("Which Amazon site do you shop on?", default="www.amazon.com")
    )

    groups = [prompt_group(1)]
    while click.confirm("\nAdd another, separate item to buy?", default=False):
        groups.append(prompt_group(len(groups) + 1))

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(build_config(website, groups), f, indent=2)
    click.secho(f"\nSaved your choices to {config_path}", fg="green")
