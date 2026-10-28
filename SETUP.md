# Setup

Commands to get Almanac running on a new machine. Run each block in a terminal and wait for it to finish before the next one. Written for Ubuntu (22.04 or later); macOS and Windows notes are at the end.

## 1. Install the system packages

Python 3.10 or later, PostgreSQL, git, and `pdftotext` (needed only to rebuild the data).

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip postgresql poppler-utils
```

## 2. Start PostgreSQL and give yourself a database role

The app connects as your Linux user with no password, so create a matching superuser role once.

```bash
sudo systemctl enable --now postgresql
sudo -u postgres createuser --superuser "$USER"
```

If the second command says the role already exists, that is fine. Check that it works:

```bash
psql -d postgres -c "select version();"
```

## 3. Clone the repo

```bash
cd ~
git clone https://github.com/dylcmonty/CPSC475.git
cd CPSC475
```

## 4. Create the Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

Run `source .venv/bin/activate` again in every new terminal before using `flask`, `python` or `pytest`.

## 5. Get the data file

The loaded data (`data/almanac.sqlite`, about 3 MB) is not in git. Pick one option.

**Option A: get the file from Dylan.** Put it at `data/almanac.sqlite`:

```bash
mkdir -p data
cp ~/Downloads/almanac.sqlite data/almanac.sqlite
```

**Option B: rebuild it from the public sources.** This downloads about 75 MB of reports into `data/raw/` and can take a while (the USDA archive is slow and sometimes returns errors; the script retries). Files already downloaded are skipped, so it is safe to rerun.

```bash
python3 loaders/fetch_usda.py
python3 loaders/fetch_county_line.py
python3 loaders/fetch_taxonomy.py
python3 loaders/fetch_farms.py
python3 loaders/build_sqlite.py
```

`build_sqlite.py` prints the row counts and every line it could not read. Newer auction reports may make the counts a little higher than 33,667 lots.

## 6. Load the database

This creates the `almanac` database, loads the schema and imports the data. It asks before dropping an existing `almanac` database.

```bash
scripts/demo.sh setup data/almanac.sqlite
```

It ends with a preflight check. Every line should be marked `ok`; a `FAIL` line says what to fix.

## 7. Run the app

```bash
scripts/demo.sh
```

This starts the app at http://127.0.0.1:5000 and opens the demo pages in the browser. Press Ctrl+C to stop it.

To run Flask directly instead:

```bash
source .venv/bin/activate
export DATABASE_URL=postgresql:///almanac
flask --app almanac run --debug
```

## 8. Run the tests

The tests create and drop their own `almanac_test` database, so they do not touch `almanac`.

```bash
source .venv/bin/activate
TEST_DATABASE_URL=postgresql:///postgres pytest
```

## Everyday commands

```bash
cd ~/CPSC475
git pull                                 # get the latest changes
source .venv/bin/activate
scripts/demo.sh check                    # preflight only, changes nothing
scripts/demo.sh                          # start the app
scripts/demo.sh reset                    # clear the demo farm after a rehearsal
psql almanac                             # open the database (\dt lists tables, \q quits)
```

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `connection refused` or `could not connect to server` | `sudo systemctl start postgresql` |
| `role "<name>" does not exist` | `sudo -u postgres createuser --superuser "$USER"` |
| `database "almanac" does not exist` | Run step 6 again |
| `No module named flask` or `psycopg` | `source .venv/bin/activate`, then `pip install -r requirements.txt` |
| `pdftotext: not found` during step 5 | `sudo apt install poppler-utils` |
| Port 5000 already in use | `PORT=5050 scripts/demo.sh` |
| `scripts/demo.sh: Permission denied` | `chmod +x scripts/demo.sh` |

## macOS

Use Homebrew for steps 1 and 2, then follow steps 3 to 8 as written.

```bash
brew install git python postgresql@16 poppler
brew services start postgresql@16
```

Homebrew's PostgreSQL already has a superuser role named after your Mac user, so skip `createuser`. If `psql` is not found, run `brew link --force postgresql@16`.

## Windows

Install WSL with Ubuntu, then do everything above inside the Ubuntu terminal:

```powershell
wsl --install -d Ubuntu
```

Restart when asked, open "Ubuntu" from the Start menu, and start at step 1. If `systemctl` does not work in WSL, use `sudo service postgresql start` instead. The app is still at http://127.0.0.1:5000 in your Windows browser.
