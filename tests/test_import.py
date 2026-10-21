"""The SQLite importer keeps keys and leaves sequences ready for new rows."""
import sqlite3
import subprocess
import sys
from pathlib import Path

import psycopg

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "import_sqlite.py"


def make_sqlite(path):
    lite = sqlite3.connect(path)
    lite.executescript("""
        CREATE TABLE observer (observer_id INTEGER PRIMARY KEY, name TEXT, domain TEXT, granularity TEXT);
        CREATE TABLE region (region_id INTEGER PRIMARY KEY, parent_region_id INTEGER, name TEXT, kind TEXT);
        CREATE TABLE taxon (taxon_id INTEGER PRIMARY KEY, parent_taxon_id INTEGER, path TEXT,
                            depth INTEGER, rank TEXT, scientific_name TEXT, common_name TEXT);
        CREATE TABLE event_kind (event_kind_code TEXT PRIMARY KEY, label TEXT, is_yield INTEGER);
        CREATE TABLE farm (farm_id INTEGER PRIMARY KEY, name TEXT, domain TEXT, region_id INTEGER,
                           owner_email TEXT, created_at TEXT);
        INSERT INTO observer VALUES (7, 'Source', NULL, 'lot');
        INSERT INTO region VALUES (11, 10, 'County', 'county'), (10, NULL, 'State', 'state');
        INSERT INTO taxon VALUES (21, 20, '20.21', 1, 'genus', 'Child', NULL),
                                 (20, NULL, '20', 0, 'family', 'Parent', NULL);
        INSERT INTO event_kind VALUES ('harvest', 'Harvested', 1), ('prune', 'Pruning', 0);
        INSERT INTO farm VALUES (5, 'Imported Farm', NULL, 11, NULL, '2026-01-01 00:00:00');
    """)
    lite.commit()
    lite.close()


def test_import_round_trip(database_url, tmp_path):
    source = tmp_path / "almanac.sqlite"
    make_sqlite(source)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(source)],
        env={"DATABASE_URL": database_url, "PATH": ""},
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "market_lot: not in the SQLite file, skipped" in result.stdout

    with psycopg.connect(database_url) as conn:
        assert conn.execute("SELECT farm_id, name FROM farm").fetchall() == [(5, "Imported Farm")]
        assert conn.execute(
            "SELECT label, is_yield FROM event_kind WHERE event_kind_code IN ('harvest', 'prune')"
            " ORDER BY 1").fetchall() == [("Harvested", True), ("Pruning", False)]
        new_id = conn.execute(
            "INSERT INTO farm (name, region_id) VALUES ('Next', 11) RETURNING farm_id").fetchone()[0]
        assert new_id == 6
