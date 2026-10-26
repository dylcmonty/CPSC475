"""Test fixtures.

The tests need a PostgreSQL server. Set TEST_DATABASE_URL to a database
on it you can connect to (for example postgresql:///postgres); each test
gets a freshly created `almanac_test` database next to it.

The rows inserted here are a small synthetic fixture for exercising the
queries, not project data.
"""
import os
from pathlib import Path

import psycopg
import pytest
from psycopg.conninfo import make_conninfo

from almanac import create_app

ADMIN_URL = os.environ.get("TEST_DATABASE_URL")
DB_DIR = Path(__file__).resolve().parent.parent / "db"
TEST_DB = "almanac_test"

FIXTURE_SQL = """
INSERT INTO observer (observer_id, name, granularity) OVERRIDING SYSTEM VALUE VALUES
    (1, 'Test Auction A', 'lot'),
    (2, 'Test Auction B', 'product_day');

INSERT INTO region (region_id, parent_region_id, name, kind) OVERRIDING SYSTEM VALUE VALUES
    (1, NULL, 'Ohio', 'state'),
    (2, 1, 'Holmes', 'county'),
    (3, 1, 'Wayne', 'county');

INSERT INTO taxon (taxon_id, parent_taxon_id, path, depth, rank, scientific_name, common_name)
OVERRIDING SYSTEM VALUE VALUES
    (1, NULL, '1',       0, 'order',   'Asparagales', NULL),
    (2, 1,    '1.2',     1, 'family',  'Amaryllidaceae', NULL),
    (3, 2,    '1.2.3',   2, 'genus',   'Allium', NULL),
    (4, 3,    '1.2.3.4', 3, 'species', 'Allium cepa', 'onion'),
    (5, 3,    '1.2.3.5', 3, 'species', 'Allium sativum', 'garlic'),
    (6, 3,    '1.2.3.6', 3, 'species', 'Allium vineale', 'wild garlic');

INSERT INTO product (product_id, slug, title, taxon_id) OVERRIDING SYSTEM VALUE VALUES
    (1, 'onion-yellow', 'Yellow onion', 4),
    (2, 'garlic', 'Garlic', 5);

INSERT INTO product_alias (label_norm, product_id, match_rung, confirmed_at) VALUES
    ('onions yellow 50lb', 1, 0, '2026-01-01'),
    ('garlic', 2, 0, '2026-01-01');

INSERT INTO market_lot (observer_id, sale_date, raw_label, label_norm, unit, quantity,
                        low_cents, high_cents, avg_cents) VALUES
    (1, '2024-07-10', 'ONIONS YELLOW 50LB', 'onions yellow 50lb', 'bag', 10, 800, 1200, 1000),
    (1, '2025-07-15', 'Onions Yellow 50lb', 'onions yellow 50lb', 'bag', 5, 900, 1300, 1100),
    (2, '2025-08-15', 'ONIONS YELLOW 50LB', 'onions yellow 50lb', 'bag', 8, 700, 1100, 900),
    (1, '2025-07-01', 'Garlic', 'garlic', 'lb', 20, 300, 500, 400),
    (1, '2025-07-25', 'Onions Yellow 50lb', 'onions yellow 50lb', 'peck', 4, 300, 500, 400),
    (2, '2025-07-02', '10" Hanging Basket', '10 hanging basket', 'each', 3, 1500, 2500, 2000);

INSERT INTO farm (farm_id, name, region_id) OVERRIDING SYSTEM VALUE VALUES
    (1, 'Test Farm', 2),
    (2, 'Other Farm', 3);
SELECT setval(pg_get_serial_sequence('farm', 'farm_id'), 2);
"""


@pytest.fixture
def database_url():
    if not ADMIN_URL:
        pytest.skip("TEST_DATABASE_URL is not set")
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
        admin.execute(f"CREATE DATABASE {TEST_DB}")
    url = make_conninfo(ADMIN_URL, dbname=TEST_DB)
    with psycopg.connect(url) as conn:
        conn.execute((DB_DIR / "schema.sql").read_text())
        conn.execute((DB_DIR / "seed.sql").read_text())
    return url


@pytest.fixture
def app(database_url):
    with psycopg.connect(database_url) as conn:
        conn.execute(FIXTURE_SQL)
    return create_app({"DATABASE_URL": database_url, "TESTING": True})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sql(database_url):
    """Run a query directly against the test database."""
    def run(statement, params=None):
        with psycopg.connect(database_url) as conn:
            return conn.execute(statement, params).fetchall()
    return run
