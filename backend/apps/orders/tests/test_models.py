"""Order / OrderItem model behaviour and the status-label mapping."""
import pytest

from apps.orders.models import (
    STATUS_CANCELLED,
    STATUS_FLOW,
    STATUS_LABELS_UK,
    STATUS_NEW,
    Order,
    OrderItem,
)
from apps.orders.schemas import OrderOut


@pytest.mark.django_db
def test_order_defaults(product_factory):
    order = Order.objects.create(
        first_name="A", last_name="B", phone="1", email="a@b.com",
        city="C", address="D",
    )
    assert order.status == STATUS_NEW
    assert order.total_price == 0
    assert order.bonus_earned == 0
    assert order.applied_bonuses == 0
    assert order.user_id is None
    assert order.session_id is None


@pytest.mark.django_db
def test_order_str():
    order = Order.objects.create(
        first_name="A", last_name="B", phone="1", email="a@b.com",
        city="C", address="D",
    )
    assert str(order) == f"Order #{order.pk} (new)"


@pytest.mark.django_db
def test_orderitem_str(product_factory):
    product = product_factory()
    order = Order.objects.create(
        first_name="A", last_name="B", phone="1", email="a@b.com",
        city="C", address="D",
    )
    item = OrderItem.objects.create(
        order=order, product=product, product_title="Snapshot",
        quantity=3, price="50.00",
    )
    assert str(item) == f"3 × Snapshot (order #{order.id})"


def test_status_choices_are_the_flow_plus_cancelled():
    keys = [key for key, _label in Order.STATUS_CHOICES]
    assert keys == STATUS_FLOW + [STATUS_CANCELLED]
    # cancelled is a terminal state outside the 4-step stepper flow.
    assert STATUS_CANCELLED not in STATUS_FLOW
    assert len(STATUS_FLOW) == 4


@pytest.mark.parametrize("status,label", list(STATUS_LABELS_UK.items()))
def test_resolve_status_label_maps_known_statuses(status, label):
    assert OrderOut.resolve_status_label({"status": status}) == label


def test_resolve_status_label_unknown_falls_back_to_raw_key():
    assert OrderOut.resolve_status_label({"status": "does-not-exist"}) == "does-not-exist"


@pytest.mark.django_db
def test_resolve_status_label_accepts_model_instance():
    order = Order.objects.create(
        first_name="A", last_name="B", phone="1", email="a@b.com",
        city="C", address="D", status=STATUS_CANCELLED,
    )
    assert OrderOut.resolve_status_label(order) == STATUS_LABELS_UK[STATUS_CANCELLED]


@pytest.mark.django_db
def test_default_ordering_is_newest_first():
    older = Order.objects.create(
        first_name="A", last_name="B", phone="1", email="a@b.com",
        city="C", address="D",
    )
    newer = Order.objects.create(
        first_name="A", last_name="B", phone="1", email="a@b.com",
        city="C", address="D",
    )
    assert list(Order.objects.values_list("id", flat=True)) == [newer.id, older.id]


@pytest.mark.django_db
def test_orderitem_reverse_relation(product_factory):
    product = product_factory()
    order = Order.objects.create(
        first_name="A", last_name="B", phone="1", email="a@b.com",
        city="C", address="D",
    )
    OrderItem.objects.create(
        order=order, product=product, product_title="X", quantity=1, price="10.00",
    )
    OrderItem.objects.create(
        order=order, product=product_factory(), product_title="Y", quantity=2,
        price="20.00",
    )
    assert order.items.count() == 2
