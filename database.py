"""
database.py — абстрактный интерфейс + две реализации: SQLite и TinyDB.

Выбор бэкенда:
    db = get_database("sqlite")   # или "tinydb"
"""

import os
import sqlite3
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

from models import Customer, Order, OrderItem, VALID_STATUSES
from logger_config import get_logger

log = get_logger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

SQLITE_PATH = os.path.join(DATA_DIR, "delivery.db")
TINYDB_PATH = os.path.join(DATA_DIR, "tinydb.json")



class AbstractDatabase(ABC):
    #Customers
    @abstractmethod
    def add_customer(self, c: Customer) -> Customer: ...
    @abstractmethod
    def get_customer(self, cid: int) -> Optional[Customer]: ...
    @abstractmethod
    def get_all_customers(self) -> List[Customer]: ...
    @abstractmethod
    def update_customer(self, c: Customer) -> bool: ...
    @abstractmethod
    def delete_customer(self, cid: int) -> bool: ...

    #Orders
    @abstractmethod
    def add_order(self, o: Order) -> Order: ...
    @abstractmethod
    def get_order(self, oid: int) -> Optional[Order]: ...
    @abstractmethod
    def get_all_orders(self) -> List[Order]: ...
    @abstractmethod
    def update_order(self, o: Order) -> bool: ...
    @abstractmethod
    def delete_order(self, oid: int) -> bool: ...
    @abstractmethod
    def filter_orders(self, status: Optional[str] = None,
                      date_from: Optional[str] = None,
                      date_to: Optional[str] = None) -> List[Order]: ...

    #Reports
    @abstractmethod
    def orders_by_status(self) -> Dict[str, int]: ...
    @abstractmethod
    def top_customers(self, n: int = 3) -> List[Dict[str, Any]]: ...
    @abstractmethod
    def revenue_for_period(self, date_from: str, date_to: str) -> float: ...

    #Bulk import
    @abstractmethod
    def bulk_import(self, customers: List[Customer], orders: List[Order]) -> None: ...



class SQLiteDatabase(AbstractDatabase):
    def __init__(self, path: str = SQLITE_PATH):
        self.path = path
        # For :memory: keep a single persistent connection
        if path == ":memory:":
            self._memory_conn = sqlite3.connect(":memory:")
            self._memory_conn.execute("PRAGMA foreign_keys = ON")
            self._memory_conn.row_factory = sqlite3.Row
        else:
            self._memory_conn = None
        self._init_db()
        log.info("SQLite DB initialised: %s", path)

    def _conn(self):
        if self._memory_conn is not None:
            return self._memory_conn
        conn = sqlite3.connect(self.path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS customers (
                    id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    name    TEXT NOT NULL,
                    phone   TEXT DEFAULT '',
                    address TEXT DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS orders (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
                    order_date  TEXT NOT NULL,
                    status      TEXT NOT NULL CHECK(status IN ('новый','в доставке','выполнен','отменён')),
                    total       REAL NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS order_items (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id     INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                    product_name TEXT NOT NULL,
                    quantity     INTEGER NOT NULL DEFAULT 1,
                    price        REAL NOT NULL DEFAULT 0
                );
            """)

    # ---- helpers ----
    def _row_to_customer(self, row) -> Customer:
        return Customer(id=row["id"], name=row["name"], phone=row["phone"], address=row["address"])

    def _load_items(self, conn, order_id: int) -> List[OrderItem]:
        rows = conn.execute(
            "SELECT * FROM order_items WHERE order_id=?", (order_id,)
        ).fetchall()
        return [OrderItem(id=r["id"], order_id=r["order_id"],
                          product_name=r["product_name"],
                          quantity=r["quantity"], price=r["price"]) for r in rows]

    def _row_to_order(self, row, conn) -> Order:
        items = self._load_items(conn, row["id"])
        cust = conn.execute("SELECT name FROM customers WHERE id=?", (row["customer_id"],)).fetchone()
        o = Order(id=row["id"], customer_id=row["customer_id"],
                  order_date=row["order_date"], status=row["status"],
                  total=row["total"], items=items)
        o.customer_name = cust["name"] if cust else ""
        return o

    #Customers
    def add_customer(self, c: Customer) -> Customer:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO customers(name,phone,address) VALUES(?,?,?)",
                (c.name, c.phone, c.address))
            c.id = cur.lastrowid
        log.info("Customer added id=%s", c.id)
        return c

    def get_customer(self, cid: int) -> Optional[Customer]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM customers WHERE id=?", (cid,)).fetchone()
        return self._row_to_customer(row) if row else None

    def get_all_customers(self) -> List[Customer]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM customers ORDER BY name").fetchall()
        return [self._row_to_customer(r) for r in rows]

    def update_customer(self, c: Customer) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE customers SET name=?,phone=?,address=? WHERE id=?",
                (c.name, c.phone, c.address, c.id))
        return cur.rowcount > 0

    def delete_customer(self, cid: int) -> bool:
        with self._conn() as conn:
            has_orders = conn.execute(
                "SELECT 1 FROM orders WHERE customer_id=? LIMIT 1", (cid,)).fetchone()
            if has_orders:
                raise ValueError("Нельзя удалить клиента с существующими заказами")
            cur = conn.execute("DELETE FROM customers WHERE id=?", (cid,))
        return cur.rowcount > 0

    #Orders
    def _save_items(self, conn, order_id: int, items: List[OrderItem]):
        conn.execute("DELETE FROM order_items WHERE order_id=?", (order_id,))
        for item in items:
            conn.execute(
                "INSERT INTO order_items(order_id,product_name,quantity,price) VALUES(?,?,?,?)",
                (order_id, item.product_name, item.quantity, item.price))

    def add_order(self, o: Order) -> Order:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO orders(customer_id,order_date,status,total) VALUES(?,?,?,?)",
                (o.customer_id, o.order_date, o.status, o.total))
            o.id = cur.lastrowid
            self._save_items(conn, o.id, o.items)
        log.info("Order added id=%s", o.id)
        return o

    def get_order(self, oid: int) -> Optional[Order]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
            return self._row_to_order(row, conn) if row else None

    def get_all_orders(self) -> List[Order]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM orders ORDER BY order_date DESC").fetchall()
            return [self._row_to_order(r, conn) for r in rows]

    def update_order(self, o: Order) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE orders SET customer_id=?,order_date=?,status=?,total=? WHERE id=?",
                (o.customer_id, o.order_date, o.status, o.total, o.id))
            self._save_items(conn, o.id, o.items)
        return cur.rowcount > 0

    def delete_order(self, oid: int) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM orders WHERE id=?", (oid,))
        return cur.rowcount > 0

    def filter_orders(self, status=None, date_from=None, date_to=None) -> List[Order]:
        sql = "SELECT * FROM orders WHERE 1=1"
        params: list = []
        if status:
            sql += " AND status=?"
            params.append(status)
        if date_from:
            sql += " AND order_date>=?"
            params.append(date_from)
        if date_to:
            sql += " AND order_date<=?"
            params.append(date_to)
        sql += " ORDER BY order_date DESC"
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_order(r, conn) for r in rows]

    #Reports
    def orders_by_status(self) -> Dict[str, int]:
        result = {s: 0 for s in VALID_STATUSES}
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM orders GROUP BY status").fetchall()
        for r in rows:
            result[r["status"]] = r["cnt"]
        return result

    def top_customers(self, n: int = 3) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT c.name, SUM(o.total) as total_sum, COUNT(o.id) as order_count
                FROM customers c JOIN orders o ON o.customer_id=c.id
                GROUP BY c.id ORDER BY total_sum DESC LIMIT ?
            """, (n,)).fetchall()
        return [{"name": r["name"], "total": r["total_sum"], "orders": r["order_count"]}
                for r in rows]

    def revenue_for_period(self, date_from: str, date_to: str) -> float:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(total),0) FROM orders WHERE order_date BETWEEN ? AND ?",
                (date_from, date_to)).fetchone()
        return float(row[0])

    def bulk_import(self, customers: List[Customer], orders: List[Order]) -> None:
        id_map: Dict[int, int] = {}
        for c in customers:
            old_id = c.id
            c.id = None
            saved = self.add_customer(c)
            if old_id is not None:
                id_map[old_id] = saved.id
        for o in orders:
            o.id = None
            o.customer_id = id_map.get(o.customer_id, o.customer_id)
            self.add_order(o)
        log.info("Bulk import done: %d customers, %d orders", len(customers), len(orders))



class TinyDatabase(AbstractDatabase):
    def __init__(self, path: str = TINYDB_PATH):
        try:
            from tinydb import TinyDB, Query
            from tinydb.storages import JSONStorage
        except ImportError:
            raise ImportError("Установите TinyDB: pip install tinydb")
        self._TinyDB = TinyDB
        self._Query = Query
        self.path = path
        self.db = TinyDB(path, ensure_ascii=False, encoding="utf-8")
        self._customers = self.db.table("customers")
        self._orders = self.db.table("orders")
        log.info("TinyDB initialised: %s", path)

    
    def _next_id(self, table) -> int:
        docs = table.all()
        return max((d.get("id", 0) for d in docs), default=0) + 1

    
    def add_customer(self, c: Customer) -> Customer:
        c.id = self._next_id(self._customers)
        self._customers.insert(c.to_dict())
        log.info("TinyDB customer added id=%s", c.id)
        return c

    def get_customer(self, cid: int) -> Optional[Customer]:
        Q = self._Query()
        rows = self._customers.search(Q.id == cid)
        return Customer.from_dict(rows[0]) if rows else None

    def get_all_customers(self) -> List[Customer]:
        return sorted([Customer.from_dict(r) for r in self._customers.all()],
                      key=lambda c: c.name)

    def update_customer(self, c: Customer) -> bool:
        Q = self._Query()
        updated = self._customers.update(c.to_dict(), Q.id == c.id)
        return bool(updated)

    def delete_customer(self, cid: int) -> bool:
        Q = self._Query()
        has_orders = self._orders.search(Q.customer_id == cid)
        if has_orders:
            raise ValueError("Нельзя удалить клиента с существующими заказами")
        removed = self._customers.remove(Q.id == cid)
        return bool(removed)

    
    def add_order(self, o: Order) -> Order:
        o.id = self._next_id(self._orders)
        self._orders.insert(o.to_dict())
        log.info("TinyDB order added id=%s", o.id)
        return o

    def get_order(self, oid: int) -> Optional[Order]:
        Q = self._Query()
        rows = self._orders.search(Q.id == oid)
        if not rows:
            return None
        o = Order.from_dict(rows[0])
        self._enrich_customer_name(o)
        return o

    def get_all_orders(self) -> List[Order]:
        orders = [Order.from_dict(r) for r in self._orders.all()]
        for o in orders:
            self._enrich_customer_name(o)
        return sorted(orders, key=lambda x: x.order_date, reverse=True)

    def _enrich_customer_name(self, o: Order):
        c = self.get_customer(o.customer_id)
        o.customer_name = c.name if c else ""

    def update_order(self, o: Order) -> bool:
        Q = self._Query()
        updated = self._orders.update(o.to_dict(), Q.id == o.id)
        return bool(updated)

    def delete_order(self, oid: int) -> bool:
        Q = self._Query()
        removed = self._orders.remove(Q.id == oid)
        return bool(removed)

    def filter_orders(self, status=None, date_from=None, date_to=None) -> List[Order]:
        all_orders = self.get_all_orders()
        result = []
        for o in all_orders:
            if status and o.status != status:
                continue
            if date_from and o.order_date < date_from:
                continue
            if date_to and o.order_date > date_to:
                continue
            result.append(o)
        return result

    def orders_by_status(self) -> Dict[str, int]:
        counts = {s: 0 for s in VALID_STATUSES}
        for o in self.get_all_orders():
            if o.status in counts:
                counts[o.status] += 1
        return counts

    def top_customers(self, n: int = 3) -> List[Dict[str, Any]]:
        totals: Dict[int, float] = {}
        order_counts: Dict[int, int] = {}
        for o in self.get_all_orders():
            totals[o.customer_id] = totals.get(o.customer_id, 0) + o.total
            order_counts[o.customer_id] = order_counts.get(o.customer_id, 0) + 1
        sorted_ids = sorted(totals, key=lambda cid: totals[cid], reverse=True)[:n]
        result = []
        for cid in sorted_ids:
            c = self.get_customer(cid)
            result.append({
                "name": c.name if c else f"ID {cid}",
                "total": totals[cid],
                "orders": order_counts[cid],
            })
        return result

    def revenue_for_period(self, date_from: str, date_to: str) -> float:
        return sum(o.total for o in self.filter_orders(date_from=date_from, date_to=date_to))

    def bulk_import(self, customers: List[Customer], orders: List[Order]) -> None:
        id_map: Dict[int, int] = {}
        for c in customers:
            old_id = c.id
            c.id = None
            saved = self.add_customer(c)
            if old_id is not None:
                id_map[old_id] = saved.id
        for o in orders:
            o.id = None
            o.customer_id = id_map.get(o.customer_id, o.customer_id)
            self.add_order(o)
        log.info("TinyDB bulk import done: %d customers, %d orders", len(customers), len(orders))



def get_database(backend: str = "sqlite") -> AbstractDatabase:
    if backend == "sqlite":
        return SQLiteDatabase()
    elif backend == "tinydb":
        return TinyDatabase()
    else:
        raise ValueError(f"Неизвестный бэкенд: {backend}. Используйте 'sqlite' или 'tinydb'.")
