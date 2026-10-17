from decimal import Decimal

import pytest
from lxml import html

from stores.amazon import (
    AmazonItemCondition,
    FREE_SHIPPING_PRICE,
    get_alt_shipping_costs,
    get_item_condition,
    get_shipping_costs,
    get_shipping_costs_v2,
    get_shipping_costs_v3,
    in_reserve_range,
    is_free_shipping_text,
    join_xpaths,
)


def tree(markup):
    return html.fromstring(f"<div>{markup}</div>")


@pytest.mark.parametrize(
    "total, expected",
    [
        (Decimal("10.00"), True),
        (Decimal("15.00"), True),
        (Decimal("9.995"), True),  # within a cent of the minimum
        (Decimal("15.005"), True),  # within a cent of the maximum
        (Decimal("9.98"), False),
        (Decimal("15.02"), False),
    ],
)
def test_in_reserve_range(total, expected):
    assert in_reserve_range(total, 10.0, 15.0) is expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("FREE delivery", True),
        ("FREE Shipping on orders over $25", True),
        ("Prime FREE Delivery", True),
        ("", False),
        ("$5.99 shipping", False),
    ],
)
def test_is_free_shipping_text(text, expected):
    assert is_free_shipping_text(text) is expected


def test_v3_free_delivery_attribute():
    t = tree('<span data-csa-c-delivery-price="FREE delivery">x</span>')
    assert get_shipping_costs_v3(t) == FREE_SHIPPING_PRICE


def test_v3_priced_delivery_attribute():
    t = tree('<span data-csa-c-delivery-price="$5.99">x</span>')
    assert get_shipping_costs_v3(t).amount == Decimal("5.99")


def test_v3_unparseable_attribute_falls_through():
    t = tree('<span data-csa-c-delivery-price="Tomorrow">x</span>')
    assert get_shipping_costs_v3(t) is None


def test_v2_delivery_message():
    assert get_shipping_costs_v2(
        tree('<div id="delivery-message">FREE Delivery</div>')
    ) == (FREE_SHIPPING_PRICE)
    assert get_shipping_costs_v2(
        tree('<div id="delivery-message">$12.50</div>')
    ).amount == Decimal("12.50")


def test_alt_shipping_div_with_price_spans():
    t = tree(
        '<div id="aod-bottlingDepositFee-0"></div>'
        '<div class="a-row aod-ship-charge"><span>+</span><span>S$21.44</span><span>shipping</span></div>'
    )
    assert get_alt_shipping_costs(t, []).amount == Decimal("21.44")


def test_shipping_costs_never_returns_unparsed_amount():
    # Previously "FREE DELIVERY" failed the reversed substring check, was parsed as a price with
    # amount None and crashed the stock check with `None > 0.0`
    t = tree('<span data-csa-c-delivery-price="FREE DELIVERY Tuesday">x</span>')
    assert get_shipping_costs(t).amount_float == 0


@pytest.mark.parametrize(
    "action, condition",
    [
        ("/gp/aws/cart/add.html/ref=aod_dpdsk_new_1", AmazonItemCondition.New),
        ("/gp/aws/cart/add.html/ref=aod_dpdsk_used_1", AmazonItemCondition.UsedGood),
        (
            "/gp/aws/cart/add.html/ref=aod_dpdsk_col_1",
            AmazonItemCondition.CollectibleGood,
        ),
        ("/gp/aws/cart/add.html", AmazonItemCondition.Unknown),
    ],
)
def test_get_item_condition(action, condition):
    assert get_item_condition(action) == condition


def test_condition_from_str():
    assert (
        AmazonItemCondition.from_str("Used - Like New")
        == AmazonItemCondition.UsedLikeNew
    )
    with pytest.raises(NotImplementedError):
        AmazonItemCondition.from_str("Mint")


def test_join_xpaths():
    assert join_xpaths(["//a", "//b"]) == "//a | //b"
