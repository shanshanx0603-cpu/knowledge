import sqlite3
from pathlib import Path

from app import connect_db, init_db


BASE_DIR = Path(__file__).resolve().parent
SQLITE_PATH = BASE_DIR / "knowledge.db"


TABLES = ("users", "knowledge_bases", "resources", "calls")


def sqlite_rows(conn, table):
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()]


def mysql_columns(conn, table):
    return [row["Field"] for row in conn.execute(f"SHOW COLUMNS FROM {table}").fetchall()]


def insert_rows(conn, table, rows):
    if not rows:
        return 0
    columns = mysql_columns(conn, table)
    insertable = [column for column in columns if column in rows[0]]
    placeholders = ", ".join(["%s"] * len(insertable))
    column_sql = ", ".join(f"`{column}`" for column in insertable)
    updates = ", ".join(f"`{column}` = VALUES(`{column}`)" for column in insertable if column != "id")
    sql = (
        f"INSERT INTO `{table}` ({column_sql}) VALUES ({placeholders}) "
        f"ON DUPLICATE KEY UPDATE {updates}"
    )
    values = [tuple(row.get(column) for column in insertable) for row in rows]
    conn.executemany(sql, values)
    return len(rows)


def main():
    if not SQLITE_PATH.exists():
        raise SystemExit(f"未找到 SQLite 数据库: {SQLITE_PATH}")

    init_db()
    with sqlite3.connect(SQLITE_PATH) as sqlite_conn, connect_db() as mysql_conn:
        for table in TABLES:
            rows = sqlite_rows(sqlite_conn, table)
            count = insert_rows(mysql_conn, table, rows)
            print(f"{table}: migrated {count} rows")


if __name__ == "__main__":
    main()
