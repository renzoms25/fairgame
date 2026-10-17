import json

from click.testing import CliRunner
import click

from cli.setup_wizard import (
    build_config,
    normalize_website,
    parse_asins,
    run_setup_wizard,
)


def test_parse_asins_from_links_and_bare_ids():
    asins, unrecognized = parse_asins(
        "https://www.amazon.com/Some-Product/dp/B08HR7SV3M/ref=sr_1_1?keywords=x, "
        "b07jh53m4t\nhttps://www.amazon.com/gp/product/B000000001"
    )
    assert asins == ["B08HR7SV3M", "B07JH53M4T", "B000000001"]
    assert unrecognized == []


def test_parse_asins_dedupes_and_reports_junk():
    asins, unrecognized = parse_asins("B08HR7SV3M B08HR7SV3M nope")
    assert asins == ["B08HR7SV3M"]
    assert unrecognized == ["nope"]


def test_normalize_website():
    assert normalize_website("amazon.com") == "www.amazon.com"
    assert normalize_website("https://www.amazon.co.uk/gp/cart") == "www.amazon.co.uk"
    assert normalize_website("smile.amazon.de") == "www.amazon.de"


def test_build_config_matches_template_format():
    config = build_config("www.amazon.com", [(["B07JH53M4T"], 10, 15)])
    assert config == {
        "asin_groups": 1,
        "asin_list_1": ["B07JH53M4T"],
        "reserve_min_1": 10,
        "reserve_max_1": 15,
        "amazon_website": "www.amazon.com",
    }


def test_wizard_writes_config(tmp_path):
    path = tmp_path / "amazon_config.json"
    command = click.command()(lambda: run_setup_wizard(str(path)))
    answers = "\n".join(
        [
            "n",  # not an Amazon site, rejected
            "",  # default site
            "not-a-link",  # rejected
            "https://www.amazon.com/dp/B08HR7SV3M",
            "20",
            "10",  # min > max, rejected
            "10",
            "20",
            "n",  # no more groups
        ]
    )
    result = CliRunner().invoke(command, input=answers + "\n")
    assert result.exit_code == 0, result.output
    assert json.loads(path.read_text()) == {
        "asin_groups": 1,
        "asin_list_1": ["B08HR7SV3M"],
        "reserve_min_1": 10.0,
        "reserve_max_1": 20.0,
        "amazon_website": "www.amazon.com",
    }
