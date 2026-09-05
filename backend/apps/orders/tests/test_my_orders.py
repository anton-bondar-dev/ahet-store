"""GET /api/orders/me — the authenticated buyer's own order history."""
import pytest

MY_ORDERS_URL = "/api/orders/me"


@pytest.mark.django_db
def test_my_orders_requires_authentication_401(api):
    resp = api.get(MY_ORDERS_URL)
    assert resp.status_code == 401


@pytest.mark.django_db
def test_my_orders_returns_only_the_callers_orders(
    api, bearer, make_user, order_factory
):
    me = make_user("me")
    other = make_user("other")
    mine1 = order_factory(user=me)
    mine2 = order_factory(user=me)
    order_factory(user=other)  # must not leak
    order_factory(user=None, session_id="anon")  # anonymous order, not mine

    resp = api.get(MY_ORDERS_URL, headers=bearer(me))
    assert resp.status_code == 200
    ids = {o["id"] for o in resp.json()}
    assert ids == {mine1.id, mine2.id}


@pytest.mark.django_db
def test_my_orders_are_ordered_newest_first(api, bearer, make_user, order_factory):
    me = make_user("me")
    older = order_factory(user=me)
    newer = order_factory(user=me)

    resp = api.get(MY_ORDERS_URL, headers=bearer(me))
    assert resp.status_code == 200
    ids = [o["id"] for o in resp.json()]
    assert ids == [newer.id, older.id]


@pytest.mark.django_db
def test_my_orders_empty_for_user_without_orders(api, bearer, make_user):
    user = make_user("fresh")
    resp = api.get(MY_ORDERS_URL, headers=bearer(user))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.django_db
def test_my_orders_serializes_items_and_status_label(
    api, bearer, make_user, product_factory, order_factory
):
    me = make_user("me")
    product = product_factory()
    order_factory(
        user=me, items=[(product, 3, "80.00")], status="shipped",
    )
    resp = api.get(MY_ORDERS_URL, headers=bearer(me))
    assert resp.status_code == 200
    (payload,) = resp.json()
    assert payload["status"] == "shipped"
    assert payload["status_label"] == "Відправлено"
    assert len(payload["items"]) == 1
    assert payload["items"][0]["product_title"] == product.title
    assert payload["items"][0]["quantity"] == 3
