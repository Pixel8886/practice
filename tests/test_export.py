"""
tests/test_export.py — тесты экспорта и импорта XML/JSON.
"""
import os
import sys
import json
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import Customer, Order, OrderItem
from data_export import (
    export_json, import_json,
    export_xml, import_xml,
    export_file, import_file,
    _validate_json,
)
from database import SQLiteDatabase




@pytest.fixture
def db_with_data(tmp_path):
    db = SQLiteDatabase(path=str(tmp_path / "test_export.db"))
    c1 = db.add_customer(Customer(name="Тест Клиент", phone="111", address="Адрес 1"))
    c2 = db.add_customer(Customer(name="Второй Клиент", phone="222", address="Адрес 2"))
    o1 = Order(customer_id=c1.id, order_date="2025-06-01",
               status="выполнен", total=0.0,
               items=[OrderItem(product_name="Пицца", quantity=2, price=750.0)])
    o1.recalc_total()
    o2 = Order(customer_id=c2.id, order_date="2025-06-05",
               status="новый", total=0.0,
               items=[OrderItem(product_name="Суши", quantity=1, price=500.0)])
    o2.recalc_total()
    db.add_order(o1)
    db.add_order(o2)
    return db




class TestJSONExport:
    def test_export_creates_file(self, tmp_path, db_with_data):
        path = str(tmp_path / "out.json")
        export_json(db_with_data, path)
        assert os.path.exists(path)

    def test_export_valid_json(self, tmp_path, db_with_data):
        path = str(tmp_path / "out.json")
        export_json(db_with_data, path)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert "customers" in data
        assert "orders" in data
        assert len(data["customers"]) == 2
        assert len(data["orders"]) == 2

    def test_export_items_included(self, tmp_path, db_with_data):
        path = str(tmp_path / "out.json")
        export_json(db_with_data, path)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        orders_with_items = [o for o in data["orders"] if o.get("items")]
        assert len(orders_with_items) > 0


class TestJSONImport:
    def test_import_roundtrip(self, tmp_path, db_with_data):
        path = str(tmp_path / "round.json")
        export_json(db_with_data, path)
        customers, orders = import_json(path)
        assert len(customers) == 2
        assert len(orders) == 2

    def test_import_customer_fields(self, tmp_path, db_with_data):
        path = str(tmp_path / "round.json")
        export_json(db_with_data, path)
        customers, _ = import_json(path)
        names = {c.name for c in customers}
        assert "Тест Клиент" in names

    def test_import_order_total(self, tmp_path, db_with_data):
        path = str(tmp_path / "round.json")
        export_json(db_with_data, path)
        _, orders = import_json(path)
        totals = {o.total for o in orders}
        assert 1500.0 in totals

    def test_import_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            import_json(str(tmp_path / "missing.json"))

    def test_validate_json_missing_name(self):
        with pytest.raises(ValueError, match="name"):
            _validate_json({"customers": [{"phone": "111"}], "orders": []})

    def test_validate_json_invalid_status(self):
        bad = {
            "customers": [{"name": "X"}],
            "orders": [{
                "customer_id": 1,
                "order_date": "2025-01-01",
                "status": "плохой",
                "total": 100,
            }]
        }
        with pytest.raises(ValueError, match="статус"):
            _validate_json(bad)

    def test_validate_json_missing_field(self):
        bad = {
            "customers": [{"name": "X"}],
            "orders": [{"customer_id": 1, "order_date": "2025-01-01"}]
        }
        with pytest.raises(ValueError, match="status"):
            _validate_json(bad)




class TestXMLExport:
    def test_export_creates_file(self, tmp_path, db_with_data):
        path = str(tmp_path / "out.xml")
        export_xml(db_with_data, path)
        assert os.path.exists(path)

    def test_export_valid_xml(self, tmp_path, db_with_data):
        import xml.etree.ElementTree as ET
        path = str(tmp_path / "out.xml")
        export_xml(db_with_data, path)
        tree = ET.parse(path)
        root = tree.getroot()
        assert root.tag == "delivery_system"
        customers = root.findall("customers/customer")
        orders = root.findall("orders/order")
        assert len(customers) == 2
        assert len(orders) == 2

    def test_export_items_in_xml(self, tmp_path, db_with_data):
        import xml.etree.ElementTree as ET
        path = str(tmp_path / "out.xml")
        export_xml(db_with_data, path)
        tree = ET.parse(path)
        items = tree.getroot().findall("orders/order/items/item")
        assert len(items) >= 2


class TestXMLImport:
    def test_import_roundtrip(self, tmp_path, db_with_data):
        path = str(tmp_path / "round.xml")
        export_xml(db_with_data, path)
        customers, orders = import_xml(path)
        assert len(customers) == 2
        assert len(orders) == 2

    def test_import_order_status(self, tmp_path, db_with_data):
        path = str(tmp_path / "round.xml")
        export_xml(db_with_data, path)
        _, orders = import_xml(path)
        statuses = {o.status for o in orders}
        assert "выполнен" in statuses
        assert "новый" in statuses

    def test_import_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            import_xml(str(tmp_path / "missing.xml"))

    def test_import_invalid_xml(self, tmp_path):
        bad = tmp_path / "bad.xml"
        bad.write_text("<not_valid><<</not_valid>")
        with pytest.raises(ValueError, match="XML"):
            import_xml(str(bad))

    def test_import_wrong_root(self, tmp_path):
        bad = tmp_path / "bad.xml"
        bad.write_text('<?xml version="1.0"?><wrong/>')
        with pytest.raises(ValueError, match="delivery_system"):
            import_xml(str(bad))

    def test_import_invalid_status_xml(self, tmp_path):
        xml_content = '''<?xml version="1.0" encoding="utf-8"?>
<delivery_system>
  <customers><customer><id>1</id><name>X</name><phone/><address/></customer></customers>
  <orders>
    <order>
      <id>1</id><customer_id>1</customer_id>
      <order_date>2025-01-01</order_date>
      <status>плохой_статус</status>
      <total>100</total>
      <items/>
    </order>
  </orders>
</delivery_system>'''
        path = tmp_path / "bad_status.xml"
        path.write_text(xml_content, encoding="utf-8")
        with pytest.raises(ValueError, match="статус"):
            import_xml(str(path))




class TestDispatcher:
    def test_export_json_dispatch(self, tmp_path, db_with_data):
        path = str(tmp_path / "auto.json")
        export_file(db_with_data, path)
        assert os.path.exists(path)

    def test_export_xml_dispatch(self, tmp_path, db_with_data):
        path = str(tmp_path / "auto.xml")
        export_file(db_with_data, path)
        assert os.path.exists(path)

    def test_export_unknown_ext_raises(self, tmp_path, db_with_data):
        with pytest.raises(ValueError, match="формат"):
            export_file(db_with_data, str(tmp_path / "file.csv"))

    def test_import_json_dispatch(self, tmp_path, db_with_data):
        path = str(tmp_path / "auto.json")
        export_file(db_with_data, path)
        customers, orders = import_file(path)
        assert len(customers) == 2

    def test_import_xml_dispatch(self, tmp_path, db_with_data):
        path = str(tmp_path / "auto.xml")
        export_file(db_with_data, path)
        customers, orders = import_file(path)
        assert len(orders) == 2

    def test_import_unknown_ext_raises(self, tmp_path):
        with pytest.raises(ValueError, match="формат"):
            import_file(str(tmp_path / "file.csv"))
