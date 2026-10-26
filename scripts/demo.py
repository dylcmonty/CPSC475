"""Set up, check and launch the Almanac demo.

Run it through scripts/demo.sh, which creates the virtualenv first:

    ./demo.sh setup path/to/almanac.sqlite   once: fresh database + real data
    ./demo.sh check                          preflight only, changes nothing
    ./demo.sh                                preflight, start the app, open the tabs
    ./demo.sh reset                          clear the demo farm after a rehearsal

DATABASE_URL selects the database (default postgresql:///almanac).
DEMO_FARM_ID picks the demo farm by hand; otherwise the first empty farm
is chosen once and remembered in .demo-farm.
"""
import argparse
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo

ROOT = Path(__file__).resolve().parent.parent
FARM_FILE = ROOT / ".demo-farm"
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql:///almanac")
PORT = int(os.environ.get("PORT", "5000"))
BASE = f"http://127.0.0.1:{PORT}"

# The harvest the demo records. Change it here if check says it has no lots.
CROP = "Allium cepa"
HARVEST_DATE = "2025-08-12"
EXPECTED_LOTS = 33667

# Same join as the harvest vs. market page, limited to one crop and date.
LOTS_NEAR_HARVEST_SQL = """
SELECT p.title, COUNT(l.lot_id) AS lots
FROM taxon t
JOIN product p        ON p.taxon_id = t.taxon_id
JOIN product_alias a  ON a.product_id = p.product_id
JOIN market_lot l     ON l.label_norm = a.label_norm
                     AND l.sale_date BETWEEN CAST(%(day)s AS DATE) - 30
                                         AND CAST(%(day)s AS DATE) + 30
WHERE t.scientific_name = %(crop)s
GROUP BY p.title
ORDER BY lots DESC
"""

# The busiest month for the crop, offered when the harvest date is too quiet.
BEST_MONTH_SQL = """
SELECT EXTRACT(YEAR FROM v.sale_date)::INT AS year,
       EXTRACT(MONTH FROM v.sale_date)::INT AS month, COUNT(*) AS lots
FROM v_priced_lot v
JOIN taxon t ON t.taxon_id = v.taxon_id
WHERE t.scientific_name = %(crop)s
GROUP BY 1, 2
ORDER BY lots DESC, year DESC
LIMIT 1
"""

EMPTY_FARM_SQL = """
SELECT f.farm_id
FROM farm f
WHERE NOT EXISTS (SELECT 1 FROM farm_event e   WHERE e.farm_id = f.farm_id)
  AND NOT EXISTS (SELECT 1 FROM plot p         WHERE p.farm_id = f.farm_id)
  AND NOT EXISTS (SELECT 1 FROM crop_catalog c WHERE c.farm_id = f.farm_id)
ORDER BY f.domain IS NULL, f.name
LIMIT 1
"""

FARM_SQL = """
SELECT f.farm_id, f.name, r.name AS region,
       (SELECT COUNT(*) FROM farm_event e   WHERE e.farm_id = f.farm_id) AS events,
       (SELECT COUNT(*) FROM plot p         WHERE p.farm_id = f.farm_id) AS plots,
       (SELECT COUNT(*) FROM crop_catalog c WHERE c.farm_id = f.farm_id) AS crops
FROM farm f
JOIN region r ON r.region_id = f.region_id
WHERE f.farm_id = %(farm_id)s
"""

OK, WARN, FAIL = "  ok  ", "  !!  ", " FAIL "


def say(mark, text):
    print(f"[{mark}] {text}", flush=True)


def connect(url=DATABASE_URL):
    try:
        return psycopg.connect(url, connect_timeout=5)
    except psycopg.OperationalError as err:
        if "does not exist" in str(err) and "database" in str(err):
            say(FAIL, f"PostgreSQL is running, but the database in {url} does not exist yet.")
            print("         Run: ./demo.sh setup path/to/almanac.sqlite")
            sys.exit(1)
        say(FAIL, f"Cannot connect to {url}")
        print(f"         {str(err).strip().splitlines()[0]}")
        print("         Is PostgreSQL installed and running? On Ubuntu:")
        print("           sudo apt install postgresql")
        print('           sudo -u postgres createuser --superuser "$USER"')
        print("           sudo systemctl start postgresql")
        sys.exit(1)


def flask(*args):
    """Run a Flask CLI command for the app with this Python."""
    env = {**os.environ, "DATABASE_URL": DATABASE_URL}
    return subprocess.run([sys.executable, "-m", "flask", "--app", "almanac", *args],
                          cwd=ROOT, env=env, check=True)


# ---------------------------------------------------------------- setup

def setup(sqlite_file, assume_yes):
    sqlite_path = Path(sqlite_file).expanduser().resolve()
    if not sqlite_path.exists():
        sys.exit(f"No such file: {sqlite_path}")

    dbname = conninfo_to_dict(DATABASE_URL).get("dbname", "almanac")
    admin_url = make_conninfo(DATABASE_URL, dbname="postgres")
    if not assume_yes:
        answer = input(f"This drops and recreates the database '{dbname}'. Continue? [y/N] ")
        if answer.strip().lower() != "y":
            sys.exit("Stopped. Nothing changed.")

    with connect(admin_url) as admin:
        admin.autocommit = True
        admin.execute(f'DROP DATABASE IF EXISTS "{dbname}" WITH (FORCE)')
        admin.execute(f'CREATE DATABASE "{dbname}"')
    say(OK, f"Created empty database '{dbname}'")

    flask("init-db")
    env = {**os.environ, "DATABASE_URL": DATABASE_URL}
    subprocess.run([sys.executable, str(ROOT / "scripts" / "import_sqlite.py"), str(sqlite_path)],
                   cwd=ROOT, env=env, check=True)
    FARM_FILE.unlink(missing_ok=True)
    print()
    return check()


# ---------------------------------------------------------------- check

def pick_farm(conn):
    """The demo farm: DEMO_FARM_ID, else the remembered pick, else a new pick."""
    if os.environ.get("DEMO_FARM_ID"):
        return int(os.environ["DEMO_FARM_ID"])
    if FARM_FILE.exists():
        return int(FARM_FILE.read_text().strip())
    row = conn.execute(EMPTY_FARM_SQL).fetchone()
    if row is None:
        return None
    FARM_FILE.write_text(f"{row[0]}\n")
    return row[0]


def check():
    """Print what the demo needs. Returns the demo farm id, or exits on a blocker."""
    print(f"Database: {DATABASE_URL}")
    with connect() as conn:
        try:
            lots = conn.execute("SELECT COUNT(*) FROM market_lot").fetchone()[0]
        except psycopg.errors.UndefinedTable:
            say(FAIL, "The schema is missing. Run: ./demo.sh setup path/to/almanac.sqlite")
            sys.exit(1)
        if lots == 0:
            say(FAIL, "market_lot is empty. Run: ./demo.sh setup path/to/almanac.sqlite")
            sys.exit(1)
        say(OK if lots == EXPECTED_LOTS else WARN,
            f"market_lot has {lots:,} rows (expected {EXPECTED_LOTS:,})")

        farm_id = pick_farm(conn)
        farm = conn.execute(FARM_SQL, {"farm_id": farm_id}).fetchone() if farm_id else None
        if farm is None:
            say(FAIL, "No demo farm. Set DEMO_FARM_ID to a farm id from /farms/.")
            sys.exit(1)
        _, name, region, events, plots, crops = farm
        say(OK, f"Demo farm: {name} ({region} County), farm id {farm_id}")
        if events or plots or crops:
            say(WARN, f"  It already has {events} events, {plots} plots, {crops} crops "
                      "left from a rehearsal. Run: ./demo.sh reset")

        products = conn.execute(LOTS_NEAR_HARVEST_SQL,
                                {"crop": CROP, "day": HARVEST_DATE}).fetchall()
        total = sum(n for _, n in products)
        if total:
            say(OK, f"Onion has {total} auction lots within 30 days of {HARVEST_DATE}")
            say(OK, f"  Harvest date to type: {HARVEST_DATE}")
            say(OK, f"  Market product to pick: {products[0][0]} ({products[0][1]} lots)")
        else:
            say(WARN, f"Onion has no auction lots within 30 days of {HARVEST_DATE}")
            best = conn.execute(BEST_MONTH_SQL, {"crop": CROP}).fetchone()
            if best:
                say(WARN, f"  Use {best[0]}-{best[1]:02d}-15 as the harvest date instead "
                          f"({best[2]} lots that month), or set HARVEST_DATE in scripts/demo.py")
    return farm_id


# ---------------------------------------------------------------- reset

def reset(assume_yes):
    with connect() as conn:
        farm_id = pick_farm(conn)
        farm = conn.execute(FARM_SQL, {"farm_id": farm_id}).fetchone() if farm_id else None
        if farm is None:
            sys.exit("No demo farm chosen yet. Run ./demo.sh check first.")
        _, name, _, events, plots, crops = farm
        if not (events or plots or crops):
            say(OK, f"{name} is already empty.")
            return
        print(f"Remove {events} events, {plots} plots and {crops} catalog crops from {name}?")
        if not assume_yes and input("[y/N] ").strip().lower() != "y":
            sys.exit("Stopped. Nothing changed.")
        for table in ("farm_event", "plot", "crop_catalog"):
            conn.execute(f"DELETE FROM {table} WHERE farm_id = %s", (farm_id,))
    say(OK, f"{name} is empty again.")


# ---------------------------------------------------------------- start

def app_is_up():
    try:
        with urllib.request.urlopen(BASE + "/", timeout=2) as response:
            return response.status == 200
    except OSError:
        return False


def open_tabs(farm_id):
    for path in ("/", f"/farms/{farm_id}", "/search"):
        webbrowser.open_new_tab(BASE + path)
        time.sleep(0.7)


def start():
    farm_id = check()
    print()
    if app_is_up():
        say(OK, f"The app is already running at {BASE}. Opening the tabs.")
        open_tabs(farm_id)
        return

    env = {**os.environ, "DATABASE_URL": DATABASE_URL}
    server = subprocess.Popen(
        [sys.executable, "-m", "flask", "--app", "almanac", "run", "--port", str(PORT)],
        cwd=ROOT, env=env)
    try:
        for _ in range(40):
            if app_is_up():
                break
            if server.poll() is not None:
                sys.exit("The app stopped while starting. See the error above.")
            time.sleep(0.25)
        else:
            server.terminate()
            sys.exit(f"The app did not answer at {BASE} within 10 seconds.")
        say(OK, f"App running at {BASE}")
        open_tabs(farm_id)
        print()
        print("Leave this terminal open. Press Ctrl+C here after the talk to stop the app.")
        server.wait()
    except KeyboardInterrupt:
        server.terminate()
        server.wait()
        print("\nApp stopped.")


def main():
    parser = argparse.ArgumentParser(description="Set up, check and launch the Almanac demo.")
    sub = parser.add_subparsers(dest="command")
    p_setup = sub.add_parser("setup", help="recreate the database and load the real data")
    p_setup.add_argument("sqlite_file")
    p_setup.add_argument("-y", "--yes", action="store_true", help="do not ask first")
    sub.add_parser("check", help="preflight checks only")
    p_reset = sub.add_parser("reset", help="clear the demo farm's plots, crops and events")
    p_reset.add_argument("-y", "--yes", action="store_true", help="do not ask first")
    sub.add_parser("start", help="check, start the app and open the browser (default)")
    args = parser.parse_args()

    if args.command == "setup":
        setup(args.sqlite_file, args.yes)
    elif args.command == "check":
        check()
    elif args.command == "reset":
        reset(args.yes)
    else:
        start()


if __name__ == "__main__":
    main()
