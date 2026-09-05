"""GET /api/orders/{id} — ownership rules for the order-detail / success page.

An order is visible to the authenticated user who owns it, or to the anonymous
session that placed it; to nobody else.
"""
import pytest


def _url(order_id):
    return f"/api/orders/{order_id}"


@pytest.mark.django_db
def test_owner_can_view_own_order_with_items(
    api, bearer, make_user, product_factory, order_factory
):
    owner = make_user("owner")
    product = product_factory()
    order = order_factory(user=owner, session_id=None, items=[(product, 2, "100.00")])

    resp = api.get(_url(order.id), headers=bearer(owner))
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["id"] == order.id
    assert body["status"] == "new"
    assert body["status_label"] == "Нове"
    assert len(body["items"]) == 1
    assert body["items"][0]["product_title"] == product.title
    assert body["items"][0]["quantity"] == 2


@pytest.mark.django_db
def test_authenticated_owner_matches_by_user_regardless_of_session(
    api, bearer, make_user, order_factory
):
    owner = make_user("owner")
    # Order carries a server-side session id different from the request's.
    order = order_factory(user=owner, session_id="server-session")

    resp = api.get(_url(order.id), headers=bearer(owner, session_id="different-session"))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_stranger_cannot_view_another_users_order_404(
    api, bearer, make_user, order_factory
):
    owner = make_user("owner")
    stranger = make_user("stranger")
    order = order_factory(user=owner, session_id=None)

    resp = api.get(_url(order.id), headers=bearer(stranger))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_anonymous_session_owner_can_view_order(api, order_factory):
    order = order_factory(user=None, session_id="sess-A")
    resp = api.get(_url(order.id), headers={"X-Session-Id": "sess-A"})
    assert resp.status_code == 200
    assert resp.json()["id"] == order.id


@pytest.mark.django_db
def test_different_session_cannot_view_order_404(api, order_factory):
    order = order_factory(user=None, session_id="sess-A")
    resp = api.get(_url(order.id), headers={"X-Session-Id": "sess-B"})
    assert resp.status_code == 404


@pytest.mark.django_db
def test_request_with_no_identity_returns_400(api, order_factory):
    order = order_factory(user=None, session_id="sess-A")
    # No Authorization and no X-Session-Id -> caller has no identity to match on.
    resp = api.get(_url(order.id))
    assert resp.status_code == 400


@pytest.mark.django_db
def test_missing_order_returns_404_for_authenticated_owner(api, bearer, make_user):
    owner = make_user("owner")
    resp = api.get(_url(999999), headers=bearer(owner))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_authenticated_stranger_still_matched_by_session_id(
    api, bearer, make_user, order_factory
):
    # An anonymous order can also be claimed by a logged-in caller whose request
    # carries the matching session id (the owner Q ORs user OR session).
    someone = make_user("someone")
    order = order_factory(user=None, session_id="shared-session")

    resp = api.get(_url(order.id), headers=bearer(someone, session_id="shared-session"))
    assert resp.status_code == 200
