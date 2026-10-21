"""Database connection and query helpers.

One psycopg connection per request, stored on flask.g. All SQL is
hand-written and every value is passed as a bound parameter.
"""
from pathlib import Path

import click
import psycopg
from flask import current_app, g
from psycopg.rows import dict_row

DB_DIR = Path(__file__).resolve().parent.parent / "db"


def get_db():
    if "db" not in g:
        g.db = psycopg.connect(current_app.config["DATABASE_URL"], row_factory=dict_row)
    return g.db


def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, params=None):
    """Run a SELECT and return every row as a dict."""
    with get_db().cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def query_one(sql, params=None):
    """Run a SELECT and return the first row, or None."""
    with get_db().cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def execute(sql, params=None):
    """Run one write statement and commit it.

    Returns the RETURNING row if the statement has one, otherwise the
    number of rows affected. On any database error the transaction is
    rolled back and the error re-raised for the caller to report.
    """
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(sql, params)
            result = cur.fetchone() if cur.description else cur.rowcount
        db.commit()
        return result
    except psycopg.Error:
        db.rollback()
        raise


@click.command("init-db")
def init_db_command():
    """Create the schema and seed the event vocabulary."""
    with psycopg.connect(current_app.config["DATABASE_URL"]) as conn:
        conn.execute((DB_DIR / "schema.sql").read_text())
        conn.execute((DB_DIR / "seed.sql").read_text())
    click.echo("Schema created.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
