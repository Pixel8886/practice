from dataclasses import dataclass, field
from typing import List, Optional


VALID_STATUSES = ("новый", "в доставке", "выполнен", "отменён")


@dataclass
class OrderItem:
    product_name: str
    quantity: int
    price: float
    id: Optional[int] = None
    order_id: Optional[int] = None

    def subtotal(self) -> float:
        return self.quantity * self.price

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "order_id": self.order_id,
            "product_name": self.product_name,
            "quantity": self.quantity,
            "price": self.price,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "OrderItem":
        return cls(
            id=d.get("id"),
            order_id=d.get("order_id"),
            product_name=d["product_name"],
            quantity=int(d["quantity"]),
            price=float(d["price"]),
        )


@dataclass
class Customer:
    name: str
    phone: str = ""
    address: str = ""
    id: Optional[int] = None

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "phone": self.phone, "address": self.address}

    @classmethod
    def from_dict(cls, d: dict) -> "Customer":
        return cls(
            id=d.get("id"),
            name=d["name"],
            phone=d.get("phone", ""),
            address=d.get("address", ""),
        )


@dataclass
class Order:
    customer_id: int
    order_date: str
    status: str
    total: float
    items: List[OrderItem] = field(default_factory=list)
    id: Optional[int] = None
    customer_name: Optional[str] = None  # joined field for display

    def __post_init__(self):
        if self.status not in VALID_STATUSES:
            raise ValueError(f"Недопустимый статус: {self.status}. Допустимые: {VALID_STATUSES}")

    def recalc_total(self):
        self.total = sum(i.subtotal() for i in self.items)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "order_date": self.order_date,
            "status": self.status,
            "total": self.total,
            "items": [i.to_dict() for i in self.items],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Order":
        items = [OrderItem.from_dict(i) for i in d.get("items", [])]
        return cls(
            id=d.get("id"),
            customer_id=int(d["customer_id"]),
            order_date=d["order_date"],
            status=d["status"],
            total=float(d["total"]),
            items=items,
        )
