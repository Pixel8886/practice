"""
tests/test_models.py — тесты классов Customer, Order, OrderItem.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import Customer, Order, OrderItem, VALID_STATUSES


class TestOrderItem:
    def test_subtotal(self):
        item = OrderItem(product_name="Пицца", quantity=3, price=500.0)
        assert item.subtotal() == pytest.approx(1500.0)

    def test_to_dict_from_dict(self):
        item = OrderItem(id=1, order_id=10, product_name="Суши", quantity=2, price=300.0)
        d = item.to_dict()
        restored = OrderItem.from_dict(d)
        assert restored.product_name == "Суши"
        assert restored.quantity == 2
        assert restored.price == pytest.approx(300.0)

    def test_from_dict_string_values(self):
        d = {"product_name": "Бургер", "quantity": "4", "price": "250.5"}
        item = OrderItem.from_dict(d)
        assert item.quantity == 4
        assert item.price == pytest.approx(250.5)


class TestCustomer:
    def test_defaults(self):
        c = Customer(name="Анна")
        assert c.phone == ""
        assert c.address == ""
        assert c.id is None

    def test_to_dict(self):
        c = Customer(id=5, name="Анна", phone="111", address="Адрес")
        d = c.to_dict()
        assert d == {"id": 5, "name": "Анна", "phone": "111", "address": "Адрес"}

    def test_from_dict(self):
        d = {"id": 3, "name": "Борис", "phone": "+7999", "address": "СПб"}
        c = Customer.from_dict(d)
        assert c.id == 3
        assert c.name == "Борис"

    def test_from_dict_minimal(self):
        c = Customer.from_dict({"name": "Минимум"})
        assert c.name == "Минимум"
        assert c.phone == ""
        assert c.id is None


class TestOrder:
    def _make_order(self, status="новый"):
        return Order(customer_id=1, order_date="2025-01-01", status=status, total=0.0)

    def test_valid_statuses(self):
        for s in VALID_STATUSES:
            o = self._make_order(s)
            assert o.status == s

    def test_invalid_status_raises(self):
        with pytest.raises(ValueError, match="Недопустимый статус"):
            Order(customer_id=1, order_date="2025-01-01", status="неверный", total=0.0)

    def test_recalc_total(self):
        o = self._make_order()
        o.items = [
            OrderItem(product_name="А", quantity=2, price=100.0),
            OrderItem(product_name="Б", quantity=1, price=50.0),
        ]
        o.recalc_total()
        assert o.total == pytest.approx(250.0)

    def test_recalc_total_empty(self):
        o = self._make_order()
        o.recalc_total()
        assert o.total == pytest.approx(0.0)

    def test_to_dict(self):
        o = Order(id=7, customer_id=2, order_date="2025-03-15",
                  status="выполнен", total=999.0,
                  items=[OrderItem(product_name="X", quantity=1, price=999.0)])
        d = o.to_dict()
        assert d["id"] == 7
        assert d["status"] == "выполнен"
        assert len(d["items"]) == 1

    def test_from_dict_roundtrip(self):
        o = Order(id=1, customer_id=3, order_date="2025-05-10",
                  status="в доставке", total=500.0,
                  items=[OrderItem(product_name="Ролл", quantity=4, price=125.0)])
        d = o.to_dict()
        restored = Order.from_dict(d)
        assert restored.customer_id == 3
        assert restored.status == "в доставке"
        assert restored.total == pytest.approx(500.0)
        assert len(restored.items) == 1
        assert restored.items[0].product_name == "Ролл"

    def test_from_dict_no_items(self):
        d = {"customer_id": 1, "order_date": "2025-01-01",
             "status": "отменён", "total": "0"}
        o = Order.from_dict(d)
        assert o.items == []

    def test_valid_statuses_list(self):
        assert "новый" in VALID_STATUSES
        assert "в доставке" in VALID_STATUSES
        assert "выполнен" in VALID_STATUSES
        assert "отменён" in VALID_STATUSES
        assert len(VALID_STATUSES) == 4
