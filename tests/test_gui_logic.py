import pytest

from cli.setup_wizard import build_config
from gui.logic import (
    DEFAULT_OPTIONS,
    build_bot_args,
    format_log_line,
    items_from_config,
    load_options,
    parse_price_input,
    save_options,
    status_for_line,
)


def test_default_args_are_a_safe_test_run():
    assert build_bot_args(DEFAULT_OPTIONS) == [
        "amazon",
        "--test",
        "--log-stock-check",
        "--disable-presence",
        "--delay",
        "3",
    ]


def test_real_run_with_options():
    options = dict(
        DEFAULT_OPTIONS,
        test=False,
        used=True,
        sounds=False,
        discord=True,
        log_stock_check=False,
        delay=4.5,
    )
    assert build_bot_args(options) == [
        "amazon",
        "--used",
        "--disable-sound",
        "--delay",
        "4.5",
    ]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("10", 10.0),
        ("$1,299.99", 1299.99),
        ("12,50 €", 12.5),
        ("£ 49.5", 49.5),
        ("1.000,50", 1000.5),
        ("1,299", 1299.0),
    ],
)
def test_parse_price_input(text, expected):
    assert parse_price_input(text) == expected


def test_parse_price_input_rejects_empty():
    with pytest.raises(ValueError):
        parse_price_input("  ")


def test_items_round_trip_through_bot_config():
    groups = [(["B07JH53M4T", "B08HR7SV3M"], 10.0, 15.0), (["B000000001"], 1.0, 2.0)]
    assert items_from_config(build_config("www.amazon.de", groups)) == (
        "www.amazon.de",
        groups,
    )


def test_options_persist_and_ignore_unknown_keys(tmp_path):
    path = str(tmp_path / "config" / "gui_settings.json")
    save_options(dict(DEFAULT_OPTIONS, used=True, bogus=1), path)
    loaded = load_options(path)
    assert loaded["used"] is True
    assert "bogus" not in loaded


def test_load_options_defaults_when_missing(tmp_path):
    assert load_options(str(tmp_path / "nope.json")) == DEFAULT_OPTIONS


def test_status_for_line():
    assert status_for_line("...|INFO|Checking stock for items.") == "Watching for stock"
    assert "Test complete" in status_for_line(
        "...|INFO|Found button Place your order, but this is a test"
    )
    assert status_for_line("...|DEBUG|nothing interesting") is None


def test_format_log_line():
    assert format_log_line("2026-10-17 15:39:35,123|0.7.0|WARNING|Found 1 item(s)") == (
        "15:39:35  Found 1 item(s)",
        "WARNING",
    )
    assert format_log_line("plain banner text") == ("plain banner text", None)
