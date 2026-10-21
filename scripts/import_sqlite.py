"""Copy the reference data from the original SQLite database into PostgreSQL.

The schema was first built and loaded on SQLite with the same tables
and columns. This script moves every row across, keeping primary keys
so all foreign keys still line up, then resets the identity sequences
so new rows continue after the imported ones.

Usage:
    flask --app almanac init-db
    python scripts/import_sqlite.py path/to/almanac.sqlite

DATABASE_URL selects the PostgreSQL database (default postgresql:///almanac).
"""
import argparse
import os
import sqlite3
import sys

import psycopg

# Parents before children, so foreign keys are satisfied as rows arrive.
TABLES = [
    ("observer", "observer_id"),
    ("region", "region_id"),
    ("taxon", "taxon_id"),
    ("product", "product_id"),
    ("product_alias", None),
    ("market_lot", "lot_id"),
    ("market_lot_quarantine", "quarantine_id"),
    ("event_kind", None),
    ("farm", "farm_id"),
    ("plot", "plot_id"),
    ("crop_catalog", None),
    ("farm_event", "event_id"),
]

# Self-referencing tables are ordered so every parent is copied first.
ORDER_BY = {
    "region": "parent_region_id IS NOT NULL, parent_region_id, region_id",
    "taxon": "depth, taxon_id",
}


def columns_in_both(lite, pg, table):
    lite_cols = [row[1] for row in lite.execute(f"PRAGMA table_info({table})")]
    pg_cols = [row[0] for row in pg.execute(
        "SELECT column_name FROM information_schema.columns"
        " WHERE table_name = %s ORDER BY ordinal_position", (table,))]
    return [c for c in pg_cols if c in lite_cols]


def copy_table(lite, pg, table, id_column):
    columns = columns_in_both(lite, pg, table)
    if not columns:
        print(f"  {table}: not in the SQLite file, skipped")
        return
    column_list = ", ".join(columns)
    order = ORDER_BY.get(table, "rowid")
    rows = lite.execute(f"SELECT {column_list} FROM {table} ORDER BY {order}")

    if table == "event_kind":
        # The seed already inserted the standard kinds; let the file's win.
        sql = (f"INSERT INTO event_kind ({column_list}) VALUES "
               f"({', '.join(['%s'] * len(columns))}) "
               "ON CONFLICT (event_kind_code) DO UPDATE SET "
               + ", ".join(f"{c} = EXCLUDED.{c}" for c in columns if c != "event_kind_code"))
        bool_at = columns.index("is_yield") if "is_yield" in columns else None
        data = [tuple(bool(v) if i == bool_at else v for i, v in enumerate(r)) for r in rows]
        with pg.cursor() as cur:
            cur.executemany(sql, data)
        count = len(data)
    else:
        count = 0
        with pg.cursor().copy(f"COPY {table} ({column_list}) FROM STDIN") as copy:
            for row in rows:
                copy.write_row(row)
                count += 1

    if id_column:
        pg.execute(
            f"SELECT setval(pg_get_serial_sequence('{table}', '{id_column}'),"
            f" COALESCE((SELECT MAX({id_column}) FROM {table}), 0) + 1, false)")
    print(f"  {table}: {count:,} rows")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("sqlite_file")
    args = parser.parse_args()

    if not os.path.exists(args.sqlite_file):
        sys.exit(f"No such file: {args.sqlite_file}")
    lite = sqlite3.connect(args.sqlite_file)
    url = os.environ.get("DATABASE_URL", "postgresql:///almanac")

    with psycopg.connect(url) as pg:
        print(f"Importing {args.sqlite_file}")
        for table, id_column in TABLES:
            copy_table(lite, pg, table, id_column)
    print("Done.")


if __name__ == "__main__":
    main()
