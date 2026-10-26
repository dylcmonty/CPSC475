"""Turn downloaded market reports into price rows.

Each parser yields one dict per priced line:
    sale_date, commodity, variant, unit, quantity, low, high, avg
Prices are in dollars as printed; build_sqlite.py converts them to cents.
Lines that look like prices but cannot be read are reported, not guessed.
"""
import re
import subprocess
from datetime import date
from decimal import Decimal

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], start=1)}

NUM = r"(\d*\.?\d+)"


def month_number(word):
    word = word.lower()
    for name, number in MONTHS.items():
        if name.startswith(word[:3]):
            return number
    raise ValueError(word)


# ---------------------------------------------------------------- USDA

# The sale date line is typed by hand and varies: "Prices for Wednesday,
# September 2, 2026", "PRICES TO GROWERS FOR WEDNESDAY 05-JUNE-2019",
# "Prices to Growers for Monday 14-August, 2023", "MONDAY 10-JUNE 2019".
USDA_DATE_LINE = re.compile(r"prices\b.*\b(mon|tue|wed|wen|thu|fri|sat|sun)[a-z]*day\b", re.I)
MONTH_WORD = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b", re.I)
USDA_TAIL = re.compile(rf"^(?P<text>.*?)\s+(?P<qty>\d[\d,]*)\s+{NUM}\s+{NUM}\s+{NUM}\s*$")


def usda_sale_date(text):
    """The sale date from the report, or None if it is missing."""
    for line in text.splitlines():
        if not USDA_DATE_LINE.search(line):
            continue
        rest = line[USDA_DATE_LINE.search(line).end():]
        month = MONTH_WORD.search(rest)
        year = re.search(r"\b(\d{4})\b", rest)
        day = re.search(r"(?<!\d)(\d{1,2})(?!\d)", rest)
        if month and year and day:
            return date(int(year.group(1)), month_number(month.group(1)), int(day.group(1)))
    return None


def parse_usda(path):
    """Rows from one AM_FV160 text report, plus a list of unread lines."""
    text = path.read_text(errors="replace")
    try:
        sale_date = usda_sale_date(text)
    except ValueError:
        sale_date = None                  # e.g. "74-SEPTEMBER-2021" in the source
    if sale_date is None:
        return [], [f"{path.name}: no readable sale date"]

    rows, problems = [], []
    commodity, unit = None, None
    for line in text.splitlines():
        if not line.strip():
            continue
        stripped = line.strip()
        if stripped.startswith("---"):
            head = stripped.lstrip("-").strip()
            name, _, rest = head.partition(":")
            commodity = name.strip()
            m = USDA_TAIL.match(rest) if rest else None
            if not m and re.search(r"\d\s+\d*\.\d", rest):
                problems.append(f"{path.name}: unreadable price line: {stripped}")
                rest = re.split(r"\s{2,}\d", rest)[0]
            unit = (m.group("text") if m else rest).strip(" ,.") or None
            if m:
                rows.append(_usda_row(sale_date, commodity, None, unit, m))
            continue
        m = USDA_TAIL.match(line)
        if not m:
            continue
        if commodity is None:
            problems.append(f"{path.name}: price line before any commodity: {stripped}")
            continue
        variant = m.group("text").strip(" ,.") or None
        rows.append(_usda_row(sale_date, commodity, variant, unit, m))
    return rows, problems


def _usda_row(sale_date, commodity, variant, unit, m):
    return {
        "sale_date": sale_date,
        "commodity": commodity,
        "variant": variant,
        "unit": unit,
        "quantity": Decimal(m.group("qty").replace(",", "")),
        "low": Decimal(m.group(3)),
        "high": Decimal(m.group(4)),
        "avg": Decimal(m.group(5)),
    }


# ---------------------------------------------------------- County Line

CL_DATE = re.compile(r"^\s*([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})\s*$")
CL_TAIL = re.compile(rf"^(?P<text>.*?)\s+(?P<qty>\d[\d,]*)\s+{NUM}\s+{NUM}\s+{NUM}\s*$")
# Text this far from the left edge is the Size column, not a product name.
CL_UNIT_INDENT = 12


def pdf_text(path):
    return subprocess.run(["pdftotext", "-layout", str(path), "-"],
                          capture_output=True, text=True, check=True).stdout


def parse_county_line(path):
    """Rows from one County Line market report PDF, plus unread lines."""
    text = pdf_text(path)
    sale_date = None
    for line in text.splitlines()[:6]:
        m = CL_DATE.match(line)
        if m:
            sale_date = date(int(m.group(3)), month_number(m.group(1)), int(m.group(2)))
            break
    if sale_date is None:
        return [], [f"{path.name}: no sale date"]

    rows, problems = [], []
    section, commodity, variant = None, None, None
    for raw in text.splitlines():
        line = raw.replace("$", " ").rstrip()
        if not line.strip() or "Market Report" in line or CL_DATE.match(line):
            continue
        if re.match(r"^\s*Product\s+Size", line):
            continue
        indent = len(line) - len(line.lstrip())
        m = CL_TAIL.match(line)
        if not m:
            words = line.strip()
            if indent >= CL_UNIT_INDENT and words.isupper():
                section = words                      # PRODUCE, NURSERY ..., etc.
            elif _starts_upper(words):
                commodity, variant = _split_name(words)
            elif commodity:
                variant = words
            continue

        fields = re.split(r"\s{2,}", m.group("text").strip())
        if indent >= CL_UNIT_INDENT:                 # same product, another size
            unit = fields[-1]
        else:
            # Name, then Size; some rows leave Size blank.
            name, unit = (fields[0], None) if len(fields) == 1 else (" ".join(fields[:-1]), fields[-1])
            if _starts_upper(name):
                commodity, variant = _split_name(name)
            else:
                variant = name
        if commodity is None:
            problems.append(f"{path.name}: price line before any product: {raw.strip()}")
            continue
        rows.append({
            "sale_date": sale_date,
            "section": section,
            "commodity": commodity,
            "variant": variant,
            "unit": unit,
            "quantity": Decimal(m.group("qty").replace(",", "")),
            "low": Decimal(m.group(3)),
            "high": Decimal(m.group(4)),
            "avg": Decimal(m.group(5)),
        })
    return rows, problems


def _starts_upper(text):
    """Product names start with a capitalized word: 'APPLES', 'BEANS'."""
    first = text.split()[0]
    letters = [c for c in first if c.isalpha()]
    return len(letters) >= 2 and first.isupper()


def _split_name(text):
    """'APPLES Lodi' -> ('APPLES', 'Lodi'); 'BASIL PLANT' -> ('BASIL PLANT', None)."""
    words = text.split()
    upper = []
    for word in words:
        if word.isupper() or not any(c.isalpha() for c in word):
            upper.append(word)
        else:
            break
    if not upper:
        return text, None
    rest = " ".join(words[len(upper):]) or None
    return " ".join(upper), rest

