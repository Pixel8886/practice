"""
main_gui.py — GUI-интерфейс на Tkinter для системы доставки.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import date

from database import get_database, AbstractDatabase
from data_export import export_file, import_file
from models import Customer, Order, OrderItem, VALID_STATUSES
from logger_config import get_logger

log = get_logger(__name__)



class CustomerDialog(tk.Toplevel):
    def __init__(self, parent, title: str, customer: Customer = None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.result: Customer = None
        self.grab_set()

        fields = [("Имя *", "name"), ("Телефон", "phone"), ("Адрес", "address")]
        self._vars = {}
        for row, (label, key) in enumerate(fields):
            tk.Label(self, text=label, anchor="w").grid(row=row, column=0, padx=10, pady=4, sticky="w")
            var = tk.StringVar(value=getattr(customer, key, "") if customer else "")
            self._vars[key] = var
            tk.Entry(self, textvariable=var, width=35).grid(row=row, column=1, padx=10, pady=4)

        btn_frame = tk.Frame(self)
        btn_frame.grid(row=len(fields), column=0, columnspan=2, pady=10)
        tk.Button(btn_frame, text="Сохранить", command=self._save, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Отмена", command=self.destroy, width=12).pack(side="left", padx=5)
        self.wait_window()

    def _save(self):
        name = self._vars["name"].get().strip()
        if not name:
            messagebox.showerror("Ошибка", "Имя обязательно", parent=self)
            return
        self.result = Customer(
            name=name,
            phone=self._vars["phone"].get().strip(),
            address=self._vars["address"].get().strip(),
        )
        self.destroy()



class OrderDialog(tk.Toplevel):
    def __init__(self, parent, db: AbstractDatabase, order: Order = None):
        super().__init__(parent)
        self.title("Добавить заказ" if order is None else "Редактировать заказ")
        self.db = db
        self.result: Order = None
        self._items: list = list(order.items) if order else []
        self.grab_set()

        customers = db.get_all_customers()
        if not customers:
            messagebox.showerror("Ошибка", "Сначала добавьте клиента", parent=self)
            self.destroy()
            return

        self._cust_map = {f"{c.name} (ID {c.id})": c.id for c in customers}
        cust_labels = list(self._cust_map.keys())

        
        tk.Label(self, text="Клиент *").grid(row=0, column=0, padx=10, pady=4, sticky="w")
        self._cust_var = tk.StringVar()
        cust_cb = ttk.Combobox(self, textvariable=self._cust_var,
                               values=cust_labels, state="readonly", width=33)
        cust_cb.grid(row=0, column=1, padx=10, pady=4)
        if order:
            for lbl, cid in self._cust_map.items():
                if cid == order.customer_id:
                    self._cust_var.set(lbl)
                    break
        else:
            cust_cb.current(0)

        
        tk.Label(self, text="Дата (ГГГГ-ММ-ДД) *").grid(row=1, column=0, padx=10, pady=4, sticky="w")
        self._date_var = tk.StringVar(value=order.order_date if order else str(date.today()))
        tk.Entry(self, textvariable=self._date_var, width=35).grid(row=1, column=1, padx=10, pady=4)

        
        tk.Label(self, text="Статус *").grid(row=2, column=0, padx=10, pady=4, sticky="w")
        self._status_var = tk.StringVar(value=order.status if order else VALID_STATUSES[0])
        ttk.Combobox(self, textvariable=self._status_var,
                     values=list(VALID_STATUSES), state="readonly",
                     width=33).grid(row=2, column=1, padx=10, pady=4)

        
        tk.Label(self, text="Товары:").grid(row=3, column=0, columnspan=2, pady=(8, 2))
        self._items_tree = ttk.Treeview(self, columns=("name", "qty", "price"),
                                        show="headings", height=5)
        for col, text, w in [("name", "Товар", 180), ("qty", "Кол-во", 60), ("price", "Цена", 80)]:
            self._items_tree.heading(col, text=text)
            self._items_tree.column(col, width=w)
        self._items_tree.grid(row=4, column=0, columnspan=2, padx=10)
        self._refresh_items_tree()

        item_btn_frame = tk.Frame(self)
        item_btn_frame.grid(row=5, column=0, columnspan=2, pady=4)
        tk.Button(item_btn_frame, text="+ Товар", command=self._add_item, width=10).pack(side="left", padx=3)
        tk.Button(item_btn_frame, text="- Удалить", command=self._del_item, width=10).pack(side="left", padx=3)

        btn_frame = tk.Frame(self)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=10)
        tk.Button(btn_frame, text="Сохранить", command=self._save, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Отмена", command=self.destroy, width=12).pack(side="left", padx=5)
        self.wait_window()

    def _refresh_items_tree(self):
        for row in self._items_tree.get_children():
            self._items_tree.delete(row)
        for item in self._items:
            self._items_tree.insert("", "end", values=(item.product_name, item.quantity, f"{item.price:.2f}"))

    def _add_item(self):
        name = simpledialog.askstring("Товар", "Название товара:", parent=self)
        if not name:
            return
        qty = simpledialog.askinteger("Товар", "Количество:", minvalue=1, initialvalue=1, parent=self)
        if not qty:
            return
        price = simpledialog.askfloat("Товар", "Цена:", minvalue=0.0, initialvalue=0.0, parent=self)
        if price is None:
            return
        self._items.append(OrderItem(product_name=name, quantity=qty, price=price))
        self._refresh_items_tree()

    def _del_item(self):
        sel = self._items_tree.selection()
        if not sel:
            return
        idx = self._items_tree.index(sel[0])
        del self._items[idx]
        self._refresh_items_tree()

    def _save(self):
        cust_label = self._cust_var.get()
        if not cust_label:
            messagebox.showerror("Ошибка", "Выберите клиента", parent=self)
            return
        cust_id = self._cust_map[cust_label]
        order_date = self._date_var.get().strip()
        status = self._status_var.get()

        if not order_date:
            messagebox.showerror("Ошибка", "Введите дату", parent=self)
            return
        
        try:
            date.fromisoformat(order_date)
        except ValueError:
            messagebox.showerror("Ошибка", "Неверный формат даты (ГГГГ-ММ-ДД)", parent=self)
            return

        o = Order(customer_id=cust_id, order_date=order_date,
                  status=status, total=0.0, items=self._items)
        o.recalc_total()
        self.result = o
        self.destroy()




class ReportWindow(tk.Toplevel):
    def __init__(self, parent, db: AbstractDatabase):
        super().__init__(parent)
        self.title("Отчёт и аналитика")
        self.resizable(True, True)
        self.geometry("520x420")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        
        f1 = tk.Frame(nb)
        nb.add(f1, text="По статусам")
        tv1 = ttk.Treeview(f1, columns=("status", "count"), show="headings")
        tv1.heading("status", text="Статус")
        tv1.heading("count", text="Кол-во заказов")
        tv1.pack(fill="both", expand=True, padx=5, pady=5)
        for status, count in db.orders_by_status().items():
            tv1.insert("", "end", values=(status, count))

        
        f2 = tk.Frame(nb)
        nb.add(f2, text="Топ-3 клиента")
        tv2 = ttk.Treeview(f2, columns=("rank", "name", "total", "orders"), show="headings")
        for col, text, w in [("rank", "#", 30), ("name", "Клиент", 180),
                              ("total", "Сумма (руб.)", 110), ("orders", "Заказов", 70)]:
            tv2.heading(col, text=text)
            tv2.column(col, width=w)
        tv2.pack(fill="both", expand=True, padx=5, pady=5)
        for i, c in enumerate(db.top_customers(3), 1):
            tv2.insert("", "end", values=(i, c["name"], f"{c['total']:.2f}", c["orders"]))

        
        f3 = tk.Frame(nb)
        nb.add(f3, text="Выручка")
        from datetime import timedelta
        today = date.today()
        periods = [
            ("День", str(today), str(today)),
            ("Неделя", str(today - timedelta(days=6)), str(today)),
            ("Месяц", str(today.replace(day=1)), str(today)),
        ]
        tv3 = ttk.Treeview(f3, columns=("period", "revenue"), show="headings")
        tv3.heading("period", text="Период")
        tv3.heading("revenue", text="Выручка (руб.)")
        tv3.pack(fill="both", expand=True, padx=5, pady=5)
        for label, df, dt in periods:
            rev = db.revenue_for_period(df, dt)
            tv3.insert("", "end", values=(label, f"{rev:.2f}"))



class CustomersTab(tk.Frame):
    def __init__(self, parent, db: AbstractDatabase, on_change=None):
        super().__init__(parent)
        self.db = db
        self.on_change = on_change

        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", pady=4)
        tk.Button(btn_frame, text="Добавить", command=self._add).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Редактировать", command=self._edit).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Удалить", command=self._delete).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Обновить", command=self.refresh).pack(side="right", padx=4)

        self._tree = ttk.Treeview(self, columns=("id", "name", "phone", "address"), show="headings")
        for col, text, w in [("id", "ID", 40), ("name", "Имя", 200),
                              ("phone", "Телефон", 130), ("address", "Адрес", 250)]:
            self._tree.heading(col, text=text)
            self._tree.column(col, width=w)
        self._tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.refresh()

    def refresh(self):
        for row in self._tree.get_children():
            self._tree.delete(row)
        for c in self.db.get_all_customers():
            self._tree.insert("", "end", iid=str(c.id),
                              values=(c.id, c.name, c.phone, c.address))

    def _selected_id(self):
        sel = self._tree.selection()
        return int(sel[0]) if sel else None

    def _add(self):
        dlg = CustomerDialog(self, "Добавить клиента")
        if dlg.result:
            self.db.add_customer(dlg.result)
            self.refresh()
            if self.on_change:
                self.on_change()

    def _edit(self):
        cid = self._selected_id()
        if not cid:
            messagebox.showinfo("Выберите", "Выберите клиента для редактирования")
            return
        c = self.db.get_customer(cid)
        dlg = CustomerDialog(self, "Редактировать клиента", c)
        if dlg.result:
            dlg.result.id = cid
            self.db.update_customer(dlg.result)
            self.refresh()

    def _delete(self):
        cid = self._selected_id()
        if not cid:
            messagebox.showinfo("Выберите", "Выберите клиента для удаления")
            return
        if not messagebox.askyesno("Удалить?", "Удалить этого клиента?"):
            return
        try:
            self.db.delete_customer(cid)
            self.refresh()
            if self.on_change:
                self.on_change()
        except ValueError as e:
            messagebox.showerror("Ошибка", str(e))



class OrdersTab(tk.Frame):
    def __init__(self, parent, db: AbstractDatabase):
        super().__init__(parent)
        self.db = db

        
        flt = tk.Frame(self)
        flt.pack(fill="x", pady=4)
        tk.Label(flt, text="Статус:").pack(side="left", padx=4)
        self._status_var = tk.StringVar(value="Все")
        status_cb = ttk.Combobox(flt, textvariable=self._status_var,
                                 values=["Все"] + list(VALID_STATUSES),
                                 state="readonly", width=14)
        status_cb.pack(side="left")
        tk.Label(flt, text="  Дата от:").pack(side="left")
        self._df_var = tk.StringVar()
        tk.Entry(flt, textvariable=self._df_var, width=11).pack(side="left")
        tk.Label(flt, text="до:").pack(side="left")
        self._dt_var = tk.StringVar()
        tk.Entry(flt, textvariable=self._dt_var, width=11).pack(side="left")
        tk.Button(flt, text="Применить", command=self.refresh).pack(side="left", padx=6)
        tk.Button(flt, text="Сбросить", command=self._reset_filter).pack(side="left")

        
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", pady=2)
        tk.Button(btn_frame, text="Добавить", command=self._add).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Редактировать", command=self._edit).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Удалить", command=self._delete).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Обновить", command=self.refresh).pack(side="right", padx=4)

        
        cols = ("id", "customer", "date", "status", "total")
        self._tree = ttk.Treeview(self, columns=cols, show="headings")
        for col, text, w in [("id", "ID", 40), ("customer", "Клиент", 180),
                              ("date", "Дата", 100), ("status", "Статус", 120),
                              ("total", "Сумма", 90)]:
            self._tree.heading(col, text=text)
            self._tree.column(col, width=w)
        scroll = ttk.Scrollbar(self, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scroll.set)
        self._tree.pack(fill="both", expand=True, padx=4, side="left")
        scroll.pack(side="right", fill="y")
        self.refresh()

    def _reset_filter(self):
        self._status_var.set("Все")
        self._df_var.set("")
        self._dt_var.set("")
        self.refresh()

    def refresh(self):
        for row in self._tree.get_children():
            self._tree.delete(row)
        status = self._status_var.get()
        orders = self.db.filter_orders(
            status=None if status == "Все" else status,
            date_from=self._df_var.get().strip() or None,
            date_to=self._dt_var.get().strip() or None,
        )
        for o in orders:
            self._tree.insert("", "end", iid=str(o.id),
                              values=(o.id, o.customer_name or "", o.order_date,
                                      o.status, f"{o.total:.2f}"))

    def _selected_id(self):
        sel = self._tree.selection()
        return int(sel[0]) if sel else None

    def _add(self):
        dlg = OrderDialog(self, self.db)
        if dlg.result:
            self.db.add_order(dlg.result)
            self.refresh()

    def _edit(self):
        oid = self._selected_id()
        if not oid:
            messagebox.showinfo("Выберите", "Выберите заказ для редактирования")
            return
        o = self.db.get_order(oid)
        dlg = OrderDialog(self, self.db, o)
        if dlg.result:
            dlg.result.id = oid
            self.db.update_order(dlg.result)
            self.refresh()

    def _delete(self):
        oid = self._selected_id()
        if not oid:
            messagebox.showinfo("Выберите", "Выберите заказ для удаления")
            return
        if messagebox.askyesno("Удалить?", "Удалить этот заказ?"):
            self.db.delete_order(oid)
            self.refresh()



class App(tk.Tk):
    def __init__(self, backend: str = "sqlite"):
        super().__init__()
        self.title("Быстрая доставка — Учёт заказов")
        self.geometry("900x560")
        self.minsize(700, 400)

        try:
            self.db = get_database(backend)
        except ImportError as e:
            messagebox.showerror("Ошибка БД", str(e))
            self.destroy()
            return

        
        menu = tk.Menu(self)
        self.config(menu=menu)
        file_menu = tk.Menu(menu, tearoff=0)
        menu.add_cascade(label="Файл", menu=file_menu)

        
        db_menu = tk.Menu(file_menu, tearoff=0)
        self._db_var = tk.StringVar(value=backend)
        db_menu.add_radiobutton(label="SQLite", variable=self._db_var,
                                value="sqlite", command=self._switch_db)
        db_menu.add_radiobutton(label="TinyDB", variable=self._db_var,
                                value="tinydb", command=self._switch_db)
        file_menu.add_cascade(label="База данных", menu=db_menu)
        file_menu.add_separator()
        file_menu.add_command(label="Экспорт...", command=self._export)
        file_menu.add_command(label="Импорт...", command=self._import)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.quit)

        
        toolbar = tk.Frame(self, bd=1, relief="raised")
        toolbar.pack(fill="x")
        tk.Button(toolbar, text="📊 Показать отчёт",
                  command=self._show_report).pack(side="left", padx=6, pady=2)
        tk.Button(toolbar, text="⬆ Экспорт",
                  command=self._export).pack(side="left", padx=2)
        tk.Button(toolbar, text="⬇ Импорт",
                  command=self._import).pack(side="left", padx=2)
        self._db_label = tk.Label(toolbar, text=f"БД: {backend.upper()}", fg="gray")
        self._db_label.pack(side="right", padx=8)

        
        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True)

        self._orders_tab = None
        self._customers_tab = None
        self._build_tabs()

    def _build_tabs(self):
        for tab in self._nb.tabs():
            self._nb.forget(tab)

        self._orders_tab = OrdersTab(self._nb, self.db)
        self._nb.add(self._orders_tab, text="  Заказы  ")

        self._customers_tab = CustomersTab(self._nb, self.db,
                                           on_change=self._orders_tab.refresh)
        self._nb.add(self._customers_tab, text="  Клиенты  ")

    def _switch_db(self):
        backend = self._db_var.get()
        try:
            self.db = get_database(backend)
            self._db_label.config(text=f"БД: {backend.upper()}")
            self._build_tabs()
        except ImportError as e:
            messagebox.showerror("Ошибка", str(e))

    def _show_report(self):
        ReportWindow(self, self.db)

    def _export(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("XML", "*.xml"), ("Все", "*.*")],
            title="Экспорт заказов",
        )
        if path:
            try:
                export_file(self.db, path)
                messagebox.showinfo("Экспорт", f"Экспорт завершён:\n{path}")
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))

    def _import(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json"), ("XML", "*.xml"), ("Все", "*.*")],
            title="Импорт заказов",
        )
        if path:
            try:
                customers, orders = import_file(path)
                self.db.bulk_import(customers, orders)
                self._build_tabs()
                messagebox.showinfo("Импорт",
                                    f"Импортировано: {len(customers)} клиентов, {len(orders)} заказов")
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))


def main():
    import argparse
    parser = argparse.ArgumentParser(description="GUI — Быстрая доставка")
    parser.add_argument("--db", choices=["sqlite", "tinydb"], default="sqlite")
    args = parser.parse_args()
    app = App(backend=args.db)
    app.mainloop()


if __name__ == "__main__":
    main()
