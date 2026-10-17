import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


@pytest.fixture(autouse=True)
def amazon_config(monkeypatch):
    """Populate the module level amazon_config the way Amazon.__init__ would"""
    from stores import amazon

    with open(os.path.join(ROOT, "config", "fairgame.conf"), encoding="utf-8") as f:
        config = json.load(f)["AMAZON"]
    monkeypatch.setattr(amazon, "amazon_config", config)
    return config
