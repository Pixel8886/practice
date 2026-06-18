"""
tests/test_database.py — тесты для SQLite и TinyDB бэкендов.
"""
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import Customer, Order, OrderItem
from database import SQLiteDatabase, TinyDatabase


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sqlite_db(tmp_path):
    db = SQLiteDatabase(path=str(tmp_path / "test.db"))
    return db


@pytest.fixture
def tiny_db(tmp_path):
    pytest.importorskip("tinydb")
    db = TinyDatabase(path=str(tmp_path / "test.json"))
    return db


def _sample_customer():
    return Customer(name="Иван Иванов", phone="+79001234567", address="Москва, ул. Ленина, 1")


def _sample_order(customer_id: int):
    items = [
        OrderItem(product_name="Пицца", quantity=2, price=750.0),
        OrderItem(product_name="Кола", quantity=1, price=150.0),
    ]
    o = Order(customer_id=customer_id, order_date="2025-06-01",
              status="новый", total=0.0, items=items)
    o.recalc_total()
    return o


# ---------------------------------------------------------------------------
# Customer CRUD — SQLite
# ---------------------------------------------------------------------------

class TestSQLiteCustomers:
    def test_add_customer(self, sqlite_db):
        c = sqlite_db.add_customer(_sample_customer())
        assert c.id is not None
        assert c.id > 0

    def test_get_customer(self, sqlite_db):
        c = sqlite_db.add_customer(_sample_customer())
        fetched = sqlite_db.get_customer(c.id)
        assert fetched is not None
        assert fetched.name == "Иван Иванов"
        assert fetched.phone == "+79001234567"

    def test_get_all_customers(self, sqlite_db):
        sqlite_db.add_customer(Customer(name="Алиса"))
        sqlite_db.add_customer(Customer(name="Боб"))
        customers = sqlite_db.get_all_customers()
        assert len(customers) == 2

    def test_update_customer(self, sqlite_db):
        c = sqlite_db.add_customer(_sample_customer())
        c.name = "Пётр Петров"
        sqlite_db.update_customer(c)
        updated = sqlite_db.get_customer(c.id)
        assert updated.name == "Пётр Петров"

    def test_delete_customer(self, sqlite_db):
        c = sqlite_db.add_customer(_sample_customer())
        result = sqlite_db.delete_customer(c.id)
        assert result is True
        assert sqlite_db.get_customer(c.id) is None

    def test_delete_customer_with_orders_raises(self, sqlite_db):
        c = sqlite_db.add_customer(_sample_customer())
        sqlite_db.add_order(_sample_order(c.id))
        with pytest.raises(ValueError, match="Нельзя удалить клиента"):
            sqlite_db.delete_customer(c.id)

    def test_get_nonexistent_customer(self, sqlite_db):
        assert sqlite_db.get_customer(9999) is None




class TestSQLiteOrders:
    def test_add_order(self, sqlite_db):
        c = sqlite_db.add_customer(_sample_customer())
        o = sqlite_db.add_order(_sample_order(c.id))
        assert o.id is not None
        assert o.total == pytest.approx(1650.0)

    def test_get_order(self, sqlite_db):
        c = sqlite_db.add_customer(_sample_customer())
        o = sqlite_db.add_order(_sample_order(c.id))
        fetched = sqlite_db.get_order(o.id)
        assert fetched is not None
        assert fetched.status == "новый"
        assert len(fetched.items) == 2

    def test_get_all_orders(self, sqlite_db):
        c = sqlite_db.add_customer(_sample_customer())
        sqlite_db.add_order(_sample_order(c.id))
        sqlite_db.add_order(_sample_order(c.id))
        orders = sqlite_db.get_all_orders()
        assert len(orders) == 2

    def test_update_order_status(self, sqlite_db):
        c = sqlite_db.add_customer(_sample_customer())
        o = sqlite_db.add_order(_sample_order(c.id))
        o.status = "выполнен"
        sqlite_db.update_order(o)
        updated = sqlite_db.get_order(o.id)
        assert updated.status == "выполнен"

    def test_delete_order(self, sqlite_db):
        c = sqlite_db.add_customer(_sample_customer())
        o = sqlite_db.add_order(_sample_order(c.id))
        assert sqlite_db.delete_order(o.id) is True
        assert sqlite_db.get_order(o.id) is None

    def test_filter_by_status(self, sqlite_db):
        c = sqlite_db.add_customer(_sample_customer())
        o1 = _sample_order(c.id)
        o1.status = "новый"
        o2 = _sample_order(c.id)
        o2.status = "выполнен"
        sqlite_db.add_order(o1)
        sqlite_db.add_order(o2)
        result = sqlite_db.filter_orders(status="новый")
        assert len(result) == 1
        assert result[0].status == "новый"

    def test_filter_by_date(self, sqlite_db):
        c = sqlite_db.add_customer(_sample_customer())
        o1 = _sample_order(c.id)
        o1.order_date = "2025-01-15"
        o2 = _sample_order(c.id)
        o2.order_date = "2025-06-01"
        sqlite_db.add_order(o1)
        sqlite_db.add_order(o2)
        result = sqlite_db.filter_orders(date_from="2025-05-01", date_to="2025-12-31")
        assert len(result) == 1
        assert result[0].order_date == "2025-06-01"




class TestSQLiteReports:
    def _populate(self, db):
        c1 = db.add_customer(Customer(name="Алиса"))
        c2 = db.add_customer(Customer(name="Боб"))
        o1 = Order(customer_id=c1.id, order_date="2025-06-01", status="выполнен", total=1000.0)
        o2 = Order(customer_id=c1.id, order_date="2025-06-02", status="новый", total=500.0)
        o3 = Order(customer_id=c2.id, order_date="2025-06-03", status="выполнен", total=2000.0)
        db.add_order(o1)
        db.add_order(o2)
        db.add_order(o3)
        return c1, c2

    def test_orders_by_status(self, sqlite_db):
        self._populate(sqlite_db)
        counts = sqlite_db.orders_by_status()
        assert counts["выполнен"] == 2
        assert counts["новый"] == 1
        assert counts["в доставке"] == 0

    def test_top_customers(self, sqlite_db):
        self._populate(sqlite_db)
        top = sqlite_db.top_customers(3)
        assert len(top) >= 1
        assert top[0]["name"] == "Боб"  # 2000 > 1500
        assert top[0]["total"] == pytest.approx(2000.0)

    def test_revenue_for_period(self, sqlite_db):
        self._populate(sqlite_db)
        rev = sqlite_db.revenue_for_period("2025-06-01", "2025-06-30")
        assert rev == pytest.approx(3500.0)

    def test_revenue_empty_period(self, sqlite_db):
        self._populate(sqlite_db)
        rev = sqlite_db.revenue_for_period("2020-01-01", "2020-12-31")
        assert rev == pytest.approx(0.0)




class TestTinyDBCustomers:
    def test_add_and_get(self, tiny_db):
        c = tiny_db.add_customer(_sample_customer())
        fetched = tiny_db.get_customer(c.id)
        assert fetched.name == "Иван Иванов"

    def test_update(self, tiny_db):
        c = tiny_db.add_customer(_sample_customer())
        c.phone = "+70000000000"
        tiny_db.update_customer(c)
        assert tiny_db.get_customer(c.id).phone == "+70000000000"

    def test_delete(self, tiny_db):
        c = tiny_db.add_customer(_sample_customer())
        tiny_db.delete_customer(c.id)
        assert tiny_db.get_customer(c.id) is None

    def test_delete_with_orders_raises(self, tiny_db):
        c = tiny_db.add_customer(_sample_customer())
        tiny_db.add_order(_sample_order(c.id))
        with pytest.raises(ValueError):
            tiny_db.delete_customer(c.id)


class TestTinyDBOrders:
    def test_add_and_get(self, tiny_db):
        c = tiny_db.add_customer(_sample_customer())
        o = tiny_db.add_order(_sample_order(c.id))
        fetched = tiny_db.get_order(o.id)
        assert fetched.total == pytest.approx(1650.0)
        assert len(fetched.items) == 2

    def test_filter_status(self, tiny_db):
        c = tiny_db.add_customer(_sample_customer())
        o = _sample_order(c.id)
        o.status = "отменён"
        tiny_db.add_order(o)
        result = tiny_db.filter_orders(status="отменён")
        assert len(result) == 1

    def test_reports(self, tiny_db):
        c = tiny_db.add_customer(Customer(name="Тест"))
        o = Order(customer_id=c.id, order_date="2025-06-01",
                  status="выполнен", total=999.0)
        tiny_db.add_order(o)
        counts = tiny_db.orders_by_status()
        assert counts["выполнен"] == 1
        rev = tiny_db.revenue_for_period("2025-06-01", "2025-06-30")
        assert rev == pytest.approx(999.0)




class TestBulkImport:
    def test_sqlite_bulk_import(self, sqlite_db):
        customers = [Customer(id=1, name="Клиент А"), Customer(id=2, name="Клиент Б")]
        orders = [
            Order(id=1, customer_id=1, order_date="2025-05-01", status="новый", total=100.0),
            Order(id=2, customer_id=2, order_date="2025-05-02", status="выполнен", total=200.0),
        ]
        sqlite_db.bulk_import(customers, orders)
        assert len(sqlite_db.get_all_customers()) == 2
        assert len(sqlite_db.get_all_orders()) == 2

    def test_tinydb_bulk_import(self, tiny_db):
        customers = [Customer(id=10, name="Импорт Клиент")]
        orders = [Order(id=10, customer_id=10, order_date="2025-05-01",
                        status="новый", total=500.0)]
        tiny_db.bulk_import(customers, orders)
        assert len(tiny_db.get_all_customers()) == 1
        assert len(tiny_db.get_all_orders()) == 1
