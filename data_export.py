"""
data_export.py — экспорт и импорт заказов в форматах JSON и XML.
"""

import json
import os
import xml.etree.ElementTree as ET
from typing import Tuple, List

from models import Customer, Order, OrderItem
from logger_config import get_logger

log = get_logger(__name__)



def export_json(db, filepath: str) -> None:
    customers = [c.to_dict() for c in db.get_all_customers()]
    orders = [o.to_dict() for o in db.get_all_orders()]
    data = {"customers": customers, "orders": orders}
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log.info("JSON export done: %s (%d customers, %d orders)", filepath, len(customers), len(orders))
    print(f"Экспорт JSON завершён: {filepath} "
          f"({len(customers)} клиентов, {len(orders)} заказов)")


def import_json(filepath: str) -> Tuple[List[Customer], List[Order]]:
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Файл не найден: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    _validate_json(data)
    customers = [Customer.from_dict(c) for c in data.get("customers", [])]
    orders = [Order.from_dict(o) for o in data.get("orders", [])]
    log.info("JSON import done: %s (%d customers, %d orders)",
             filepath, len(customers), len(orders))
    return customers, orders


def _validate_json(data: dict) -> None:
    if not isinstance(data, dict):
        raise ValueError("JSON должен быть объектом (словарём)")
    for c in data.get("customers", []):
        if "name" not in c:
            raise ValueError(f"Клиент без поля 'name': {c}")
    for o in data.get("orders", []):
        for field in ("customer_id", "order_date", "status", "total"):
            if field not in o:
                raise ValueError(f"Заказ без поля '{field}': {o}")
        from models import VALID_STATUSES
        if o["status"] not in VALID_STATUSES:
            raise ValueError(f"Недопустимый статус '{o['status']}' в заказе {o}")



def export_xml(db, filepath: str) -> None:
    root = ET.Element("delivery_system")

    custs_el = ET.SubElement(root, "customers")
    for c in db.get_all_customers():
        el = ET.SubElement(custs_el, "customer")
        ET.SubElement(el, "id").text = str(c.id)
        ET.SubElement(el, "name").text = c.name
        ET.SubElement(el, "phone").text = c.phone
        ET.SubElement(el, "address").text = c.address

    orders_el = ET.SubElement(root, "orders")
    for o in db.get_all_orders():
        el = ET.SubElement(orders_el, "order")
        ET.SubElement(el, "id").text = str(o.id)
        ET.SubElement(el, "customer_id").text = str(o.customer_id)
        ET.SubElement(el, "order_date").text = o.order_date
        ET.SubElement(el, "status").text = o.status
        ET.SubElement(el, "total").text = str(o.total)
        items_el = ET.SubElement(el, "items")
        for item in o.items:
            it = ET.SubElement(items_el, "item")
            ET.SubElement(it, "product_name").text = item.product_name
            ET.SubElement(it, "quantity").text = str(item.quantity)
            ET.SubElement(it, "price").text = str(item.price)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(filepath, encoding="utf-8", xml_declaration=True)
    customers_count = len(db.get_all_customers())
    orders_count = len(db.get_all_orders())
    log.info("XML export done: %s", filepath)
    print(f"Экспорт XML завершён: {filepath} "
          f"({customers_count} клиентов, {orders_count} заказов)")


def import_xml(filepath: str) -> Tuple[List[Customer], List[Order]]:
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Файл не найден: {filepath}")
    try:
        tree = ET.parse(filepath)
    except ET.ParseError as e:
        raise ValueError(f"Ошибка разбора XML: {e}")

    root = tree.getroot()
    if root.tag != "delivery_system":
        raise ValueError("Корневой элемент должен быть <delivery_system>")

    customers: List[Customer] = []
    for el in root.findall("customers/customer"):
        name = _xml_text(el, "name")
        if not name:
            raise ValueError("Клиент без тега <name>")
        customers.append(Customer(
            id=_xml_int(el, "id"),
            name=name,
            phone=_xml_text(el, "phone", ""),
            address=_xml_text(el, "address", ""),
        ))

    from models import VALID_STATUSES
    orders: List[Order] = []
    for el in root.findall("orders/order"):
        status = _xml_text(el, "status", "")
        if status not in VALID_STATUSES:
            raise ValueError(f"Недопустимый статус '{status}'")
        items = []
        for it in el.findall("items/item"):
            items.append(OrderItem(
                product_name=_xml_text(it, "product_name", ""),
                quantity=_xml_int(it, "quantity", 1),
                price=_xml_float(it, "price", 0.0),
            ))
        orders.append(Order(
            id=_xml_int(el, "id"),
            customer_id=_xml_int(el, "customer_id"),
            order_date=_xml_text(el, "order_date", ""),
            status=status,
            total=_xml_float(el, "total", 0.0),
            items=items,
        ))

    log.info("XML import done: %s (%d customers, %d orders)",
             filepath, len(customers), len(orders))
    return customers, orders


def _xml_text(el, tag: str, default: str = "") -> str:
    child = el.find(tag)
    return child.text.strip() if child is not None and child.text else default


def _xml_int(el, tag: str, default: int = 0) -> int:
    v = _xml_text(el, tag)
    return int(v) if v else default


def _xml_float(el, tag: str, default: float = 0.0) -> float:
    v = _xml_text(el, tag)
    return float(v) if v else default



def export_file(db, filepath: str) -> None:
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".json":
        export_json(db, filepath)
    elif ext == ".xml":
        export_xml(db, filepath)
    else:
        raise ValueError(f"Неизвестный формат: {ext}. Используйте .json или .xml")


def import_file(filepath: str) -> Tuple[List[Customer], List[Order]]:
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".json":
        return import_json(filepath)
    elif ext == ".xml":
        return import_xml(filepath)
    else:
        raise ValueError(f"Неизвестный формат: {ext}. Используйте .json или .xml")
