# Быстрая доставка, Система учёта заказов

Внутреннее приложение для учёта заказов с поддержкой CLI и GUI, двух БД (SQLite / TinyDB) и двух форматов экспорта (JSON / XML).

---

## Структура проекта

```
delivery_system/
├── main_cli.py        # CLI-точка входа (argparse)
├── main_gui.py        # GUI-точка входа (Tkinter)
├── database.py        # Работа с БД (SQLite + TinyDB)
├── models.py          # Классы Customer, Order, OrderItem
├── data_export.py     # Экспорт/импорт XML и JSON
├── logger_config.py   # Настройка логирования
├── tests/
│   ├── conftest.py
│   ├── test_database.py
│   ├── test_models.py
│   └── test_export.py
├── logs/              # Логи (создаётся автоматически)
├── data/              # Файлы БД (создаётся автоматически)
├── requirements.txt
└── README.md
```

---

## Установка

```bash
# 1. Клонируйте / распакуйте проект
cd delivery_system

# 2. Установите зависимости
pip install -r requirements.txt
```

Зависимости:
 `pytest` - для запуска тестов
 `tinydb` - для бонусного бэкенда TinyDB (опционально)


---

## Запуск GUI

```bash
# SQLite (по умолчанию)
python main_gui.py

# TinyDB
python main_gui.py --db tinydb
```

GUI содержит:
 Вкладку **Заказы** - список, фильтр по статусу и дате, добавление/редактирование/удаление
 Вкладку **Клиенты** - CRUD
 Кнопку **Показать отчёт** - статистика в отдельном окне (по статусам, топ-3 клиента, выручка)
 Меню **Файл → Экспорт / Импорт** с выбором формата (JSON или XML)
 Меню **Файл → База данных** - переключение между SQLite и TinyDB без перезапуска

---

## Запуск CLI

### Отчёт

```bash
python main_cli.py report --period day
python main_cli.py report --period week
python main_cli.py report --period month   # по умолчанию
```

### Экспорт

```bash
python main_cli.py export --file orders_backup.json
python main_cli.py export --file orders_backup.xml
```

### Импорт

```bash
python main_cli.py import --file orders_backup.json
python main_cli.py import --file orders_backup.xml
```

### Клиенты

```bash
# Список
python main_cli.py customers list

# Добавить
python main_cli.py customers add --name "Иван Иванов" --phone "+79001234567" --address "Москва"

# Редактировать
python main_cli.py customers edit --id 1 --phone "+70000000000"

# Удалить (нельзя, если есть заказы)
python main_cli.py customers delete --id 1
```

### Заказы

```bash
# Список с фильтрацией
python main_cli.py orders list
python main_cli.py orders list --status новый
python main_cli.py orders list --date-from 2025-01-01 --date-to 2025-06-30

# Добавить заказ с товарами
python main_cli.py orders add --customer-id 1 --date 2025-06-15 --status новый \
    --items "Пицца,2,750" "Кола,1,150"

# Детали заказа
python main_cli.py orders info --id 1

# Изменить статус
python main_cli.py orders edit --id 1 --status "в доставке"

# Удалить
python main_cli.py orders delete --id 1
```

### Выбор БД в CLI

```bash
# По умолчанию SQLite
python main_cli.py --db sqlite report --period month

# TinyDB
python main_cli.py --db tinydb report --period month
```

---

## Тесты

```bash
# Запустить все тесты
pytest tests/ -v

# С отчётом о покрытии (нужен pytest-cov)
pip install pytest-cov
pytest tests/ --cov=. --cov-report=term-missing
```

---

## Логирование

Логи пишутся в `logs/app.log` (уровень DEBUG). В консоль выводятся только WARNING и выше.

---

## Форматы данных

### JSON

```json
{
  "customers": [
    {"id": 1, "name": "Иван", "phone": "+7...", "address": "..."}
  ],
  "orders": [
    {
      "id": 1, "customer_id": 1,
      "order_date": "2025-06-01",
      "status": "новый",
      "total": 1500.0,
      "items": [
        {"product_name": "Пицца", "quantity": 2, "price": 750.0}
      ]
    }
  ]
}
```

### XML

```xml
<?xml version='1.0' encoding='utf-8'?>
<delivery_system>
  <customers>
    <customer>
      <id>1</id><name>Иван</name><phone>+7...</phone><address>...</address>
    </customer>
  </customers>
  <orders>
    <order>
      <id>1</id><customer_id>1</customer_id>
      <order_date>2025-06-01</order_date>
      <status>новый</status><total>1500.0</total>
      <items>
        <item><product_name>Пицца</product_name><quantity>2</quantity><price>750.0</price></item>
      </items>
    </order>
  </orders>
</delivery_system>
```

---

## Технологии

| Компонент | Инструмент |
|-----------|-----------|
| Язык | Python 3.8+ |
| БД | SQLite (`sqlite3`) + TinyDB (`tinydb`) |
| GUI | Tkinter |
| CLI | argparse |
| Тесты | pytest |
| Логирование | logging |
| Экспорт/импорт | JSON (`json`) + XML (`xml.etree.ElementTree`) |

---

## Бонусные функции

 Поддержка двух форматов экспорта/импорта: **JSON и XML**
 Поддержка двух БД: **SQLite и TinyDB**
