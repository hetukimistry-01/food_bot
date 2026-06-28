"""
utils/database.py — SQLite helpers for The Flame & Fork ordering system.

Schema
------
orders      : id, customer, status, total, created_at, notes
order_items : id, order_id, item_name, quantity, unit_price, subtotal
"""
import sqlite3
import os
from datetime import datetime
from typing import Optional

# ── Path ──────────────────────────────────────────────────────────────────────
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH   = os.path.join(_BASE_DIR, "data", "orders.db")


# ── Connection helper ─────────────────────────────────────────────────────────
def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# ── Schema creation ───────────────────────────────────────────────────────────
def init_db() -> None:
    """Create tables if they don't already exist."""
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS orders (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            customer   TEXT    NOT NULL DEFAULT 'Guest',
            status     TEXT    NOT NULL DEFAULT 'confirmed',
            total      REAL    NOT NULL DEFAULT 0.0,
            created_at TEXT    NOT NULL,
            notes      TEXT
        );

        CREATE TABLE IF NOT EXISTS order_items (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id   INTEGER NOT NULL REFERENCES orders(id),
            item_name  TEXT    NOT NULL,
            quantity   INTEGER NOT NULL DEFAULT 1,
            unit_price REAL    NOT NULL,
            subtotal   REAL    NOT NULL
        );
    """)
    conn.commit()
    conn.close()


# ── Write helpers ─────────────────────────────────────────────────────────────
def create_order(
    items: list[dict],
    customer: str = "Guest",
    notes: str = "",
) -> dict:
    """
    Persist a new order and its line-items.

    Parameters
    ----------
    items    : list of {"item_name": str, "quantity": int, "unit_price": float}
    customer : customer display name
    notes    : optional special instructions

    Returns
    -------
    dict with keys: order_id, customer, items, total, status, created_at
    """
    total      = sum(i["quantity"] * i["unit_price"] for i in items)
    created_at = datetime.now().isoformat(sep=" ", timespec="seconds")

    conn   = _connect()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO orders (customer, status, total, created_at, notes) VALUES (?,?,?,?,?)",
        (customer, "confirmed", round(total, 2), created_at, notes or None),
    )
    order_id = cursor.lastrowid

    for item in items:
        subtotal = round(item["quantity"] * item["unit_price"], 2)
        cursor.execute(
            "INSERT INTO order_items (order_id, item_name, quantity, unit_price, subtotal) "
            "VALUES (?,?,?,?,?)",
            (order_id, item["item_name"], item["quantity"], item["unit_price"], subtotal),
        )

    conn.commit()
    conn.close()

    return {
        "order_id"  : order_id,
        "customer"  : customer,
        "items"     : items,
        "total"     : round(total, 2),
        "status"    : "confirmed",
        "created_at": created_at,
    }


# ── Read helpers ──────────────────────────────────────────────────────────────
def get_order(order_id: int) -> Optional[dict]:
    """Return a single order with its items, or None if not found."""
    conn   = _connect()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    row = cursor.fetchone()
    if row is None:
        conn.close()
        return None

    order = dict(row)
    cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
    order["items"] = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return order


def get_all_orders() -> list[dict]:
    """Return all orders (newest first) each with their items list."""
    conn   = _connect()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM orders ORDER BY id DESC")
    orders = [dict(r) for r in cursor.fetchall()]

    for order in orders:
        cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order["id"],))
        order["items"] = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return orders


def get_sales_summary() -> dict:
    """
    Aggregate stats for the dashboard.

    Returns
    -------
    {
        total_orders  : int,
        total_revenue : float,
        best_sellers  : [{"item_name": str, "total_qty": int, "total_revenue": float}, ...],
        daily_sales   : [{"date": str, "num_orders": int, "daily_revenue": float}, ...],
    }
    """
    conn   = _connect()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) AS cnt, COALESCE(SUM(total), 0) AS rev FROM orders")
    row            = cursor.fetchone()
    total_orders   = row["cnt"]
    total_revenue  = round(row["rev"], 2)

    cursor.execute("""
        SELECT   item_name,
                 SUM(quantity)  AS total_qty,
                 SUM(subtotal)  AS total_revenue
        FROM     order_items
        GROUP BY item_name
        ORDER BY total_qty DESC
        LIMIT    10
    """)
    best_sellers = [dict(r) for r in cursor.fetchall()]

    cursor.execute("""
        SELECT   DATE(created_at) AS date,
                 COUNT(*)         AS num_orders,
                 SUM(total)       AS daily_revenue
        FROM     orders
        GROUP BY DATE(created_at)
        ORDER BY date DESC
        LIMIT    30
    """)
    daily_sales = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return {
        "total_orders" : total_orders,
        "total_revenue": total_revenue,
        "best_sellers" : best_sellers,
        "daily_sales"  : daily_sales,
    }


# Auto-initialise on import so callers don't have to remember
init_db()
