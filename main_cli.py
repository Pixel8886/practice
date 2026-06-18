"""
main_cli.py — CLI-интерфейс для системы доставки.

Примеры:
    python main_cli.py --db sqlite report --period month
    python main_cli.py --db tinydb export --file orders.xml
    python main_cli.py import --file orders.json
    python main_cli.py customers list
    python main_cli.py customers add --name "Иван" --phone "+79001234567" --address "Москва"
    python main_cli.py orders list
    python main_cli.py orders add --customer-id 1 --date 2025-06-01 --status новый
"""

import argparse
import sys
from datetime import date, timedelta

from database import get_database
from data_export import export_file, import_file
from models import Customer, Order, OrderItem, VALID_STATUSES
from logger_config import get_logger

log = get_logger(__name__)




def _period_range(period: str):
    today = date.today()
    if period == "day":
        return str(today), str(today)
    elif period == "week":
        return str(today - timedelta(days=6)), str(today)
    elif period == "month":
        return str(today.replace(day=1)), str(today)
    else:
        raise ValueError(f"Неизвестный период: {period}. Используйте day/week/month")


def cmd_report(db, args):
    period = args.period
    date_from, date_to = _period_range(period)

    print(f"\n{'='*45}")
    print(f"  ОТЧЁТ за период: {period.upper()} ({date_from} — {date_to})")
    print(f"{'='*45}")

    print("\n[ Заказы по статусам ]")
    for status, count in db.orders_by_status().items():
        print(f"  {status:<15} : {count}")

    print("\n[ Топ-3 клиента по сумме заказов ]")
    top = db.top_customers(3)
    if not top:
        print("  Нет данных")
    for i, c in enumerate(top, 1):
        print(f"  {i}. {c['name']:<20} {c['total']:.2f} руб.  ({c['orders']} заказов)")

    revenue = db.revenue_for_period(date_from, date_to)
    print(f"\n[ Выручка за период ] {revenue:.2f} руб.\n")



def cmd_customers(db, args):
    sub = args.customer_cmd

    if sub == "list":
        customers = db.get_all_customers()
        if not customers:
            print("Клиентов нет.")
            return
        print(f"\n{'ID':<5} {'Имя':<25} {'Телефон':<15} {'Адрес'}")
        print("-" * 70)
        for c in customers:
            print(f"{c.id:<5} {c.name:<25} {c.phone:<15} {c.address}")

    elif sub == "add":
        c = Customer(name=args.name, phone=args.phone or "", address=args.address or "")
        db.add_customer(c)
        print(f"Клиент добавлен с ID={c.id}")

    elif sub == "edit":
        c = db.get_customer(args.id)
        if not c:
            print(f"Клиент ID={args.id} не найден")
            return
        if args.name:
            c.name = args.name
        if args.phone:
            c.phone = args.phone
        if args.address:
            c.address = args.address
        db.update_customer(c)
        print(f"Клиент ID={c.id} обновлён")

    elif sub == "delete":
        try:
            ok = db.delete_customer(args.id)
            print("Клиент удалён" if ok else "Клиент не найден")
        except ValueError as e:
            print(f"Ошибка: {e}")



def cmd_orders(db, args):
    sub = args.order_cmd

    if sub == "list":
        orders = db.filter_orders(
            status=getattr(args, "status", None),
            date_from=getattr(args, "date_from", None),
            date_to=getattr(args, "date_to", None),
        )
        if not orders:
            print("Заказов нет.")
            return
        print(f"\n{'ID':<5} {'Клиент':<20} {'Дата':<12} {'Статус':<15} {'Сумма':>10}")
        print("-" * 65)
        for o in orders:
            print(f"{o.id:<5} {(o.customer_name or ''):<20} {o.order_date:<12} "
                  f"{o.status:<15} {o.total:>10.2f}")

    elif sub == "add":
        items = []
        if args.items:
            for item_str in args.items:
                parts = item_str.split(",")
                if len(parts) != 3:
                    print(f"Формат товара: 'Название,кол-во,цена'. Получено: {item_str}")
                    return
                items.append(OrderItem(product_name=parts[0],
                                       quantity=int(parts[1]),
                                       price=float(parts[2])))
        o = Order(customer_id=args.customer_id,
                  order_date=args.date,
                  status=args.status,
                  total=0.0,
                  items=items)
        o.recalc_total()
        db.add_order(o)
        print(f"Заказ добавлен с ID={o.id}, сумма={o.total:.2f} руб.")

    elif sub == "edit":
        o = db.get_order(args.id)
        if not o:
            print(f"Заказ ID={args.id} не найден")
            return
        if args.status:
            o.status = args.status
        if args.date:
            o.order_date = args.date
        db.update_order(o)
        print(f"Заказ ID={o.id} обновлён")

    elif sub == "delete":
        ok = db.delete_order(args.id)
        print("Заказ удалён" if ok else "Заказ не найден")

    elif sub == "info":
        o = db.get_order(args.id)
        if not o:
            print(f"Заказ ID={args.id} не найден")
            return
        print(f"\nЗаказ #{o.id}")
        print(f"  Клиент  : {o.customer_name} (ID {o.customer_id})")
        print(f"  Дата    : {o.order_date}")
        print(f"  Статус  : {o.status}")
        print(f"  Товары  :")
        for item in o.items:
            print(f"    - {item.product_name} x{item.quantity} = {item.price:.2f} руб.")
        print(f"  Итого   : {o.total:.2f} руб.")



def cmd_export(db, args):
    try:
        export_file(db, args.file)
    except Exception as e:
        print(f"Ошибка экспорта: {e}")
        log.error("Export error: %s", e)
        sys.exit(1)


def cmd_import(db, args):
    try:
        customers, orders = import_file(args.file)
        db.bulk_import(customers, orders)
        print(f"Импорт завершён: {len(customers)} клиентов, {len(orders)} заказов")
    except Exception as e:
        print(f"Ошибка импорта: {e}")
        log.error("Import error: %s", e)
        sys.exit(1)



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main_cli.py",
        description="Система учёта заказов «Быстрая доставка»",
    )
    parser.add_argument(
        "--db", choices=["sqlite", "tinydb"], default="sqlite",
        help="Бэкенд базы данных (default: sqlite)"
    )

    sub = parser.add_subparsers(dest="command")

    #report
    rep = sub.add_parser("report", help="Показать отчёт")
    rep.add_argument("--period", choices=["day", "week", "month"], default="month")

    #export
    exp = sub.add_parser("export", help="Экспорт заказов")
    exp.add_argument("--file", required=True, help="Путь к файлу (.json или .xml)")

    #import
    imp = sub.add_parser("import", help="Импорт заказов")
    imp.add_argument("--file", required=True, help="Путь к файлу (.json или .xml)")

    #customers
    custs = sub.add_parser("customers", help="Управление клиентами")
    csub = custs.add_subparsers(dest="customer_cmd")

    csub.add_parser("list", help="Список клиентов")

    cadd = csub.add_parser("add", help="Добавить клиента")
    cadd.add_argument("--name", required=True)
    cadd.add_argument("--phone", default="")
    cadd.add_argument("--address", default="")

    cedit = csub.add_parser("edit", help="Редактировать клиента")
    cedit.add_argument("--id", type=int, required=True)
    cedit.add_argument("--name")
    cedit.add_argument("--phone")
    cedit.add_argument("--address")

    cdel = csub.add_parser("delete", help="Удалить клиента")
    cdel.add_argument("--id", type=int, required=True)

    #orders 
    ords = sub.add_parser("orders", help="Управление заказами")
    osub = ords.add_subparsers(dest="order_cmd")

    olist = osub.add_parser("list", help="Список заказов")
    olist.add_argument("--status", choices=VALID_STATUSES)
    olist.add_argument("--date-from", dest="date_from")
    olist.add_argument("--date-to", dest="date_to")

    oadd = osub.add_parser("add", help="Добавить заказ")
    oadd.add_argument("--customer-id", dest="customer_id", type=int, required=True)
    oadd.add_argument("--date", required=True, help="YYYY-MM-DD")
    oadd.add_argument("--status", choices=VALID_STATUSES, default="новый")
    oadd.add_argument("--items", nargs="*", metavar="Название,кол-во,цена",
                      help="Товары: 'Пицца,2,750'")

    oedit = osub.add_parser("edit", help="Редактировать заказ")
    oedit.add_argument("--id", type=int, required=True)
    oedit.add_argument("--status", choices=VALID_STATUSES)
    oedit.add_argument("--date")

    odel = osub.add_parser("delete", help="Удалить заказ")
    odel.add_argument("--id", type=int, required=True)

    oinfo = osub.add_parser("info", help="Детали заказа")
    oinfo.add_argument("--id", type=int, required=True)

    return parser



def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    try:
        db = get_database(args.db)
    except ImportError as e:
        print(f"Ошибка инициализации БД: {e}")
        sys.exit(1)

    dispatch = {
        "report": cmd_report,
        "export": cmd_export,
        "import": cmd_import,
        "customers": cmd_customers,
        "orders": cmd_orders,
    }

    handler = dispatch.get(args.command)
    if handler:
        handler(db, args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
