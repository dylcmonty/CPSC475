"""Farm directory, adding a farm, the farm overview, and the harvest
versus market price report."""
import psycopg
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from . import errors, forms
from .db import execute, query, query_one
from .main import like_pattern

bp = Blueprint("farms", __name__, url_prefix="/farms")

FARM_SQL = """
SELECT f.farm_id, f.name, f.domain, f.owner_email, f.created_at,
       r.name AS region, parent.name AS parent_region
FROM farm f
JOIN region r           ON r.region_id = f.region_id
LEFT JOIN region parent ON parent.region_id = r.parent_region_id
WHERE f.farm_id = %(farm_id)s
"""

FARM_LIST_SQL = """
SELECT f.farm_id, f.name, f.domain, r.name AS region,
       (SELECT COUNT(*) FROM farm_event e WHERE e.farm_id = f.farm_id) AS events
FROM farm f
JOIN region r ON r.region_id = f.region_id
WHERE CAST(%(pattern)s AS TEXT) IS NULL
   OR f.name ILIKE %(pattern)s
   OR r.name ILIKE %(pattern)s
ORDER BY f.name
LIMIT 100
"""

REGION_CHOICES_SQL = """
SELECT r.region_id, r.name, parent.name AS parent_name
FROM region r
LEFT JOIN region parent ON parent.region_id = r.parent_region_id
WHERE r.kind = 'county'
ORDER BY parent.name, r.name
"""

INSERT_FARM_SQL = """
INSERT INTO farm (name, domain, region_id, owner_email)
VALUES (%(name)s, %(domain)s, %(region_id)s, %(owner_email)s)
RETURNING farm_id
"""

OVERVIEW_PLOTS_SQL = """
SELECT pl.plot_id, pl.name, pl.area_sq_m, COUNT(e.event_id) AS events
FROM plot pl
LEFT JOIN farm_event e ON e.plot_id = pl.plot_id
WHERE pl.farm_id = %(farm_id)s
GROUP BY pl.plot_id, pl.name, pl.area_sq_m
ORDER BY pl.name
"""

OVERVIEW_CATALOG_SQL = """
SELECT c.taxon_id, t.common_name, t.scientific_name, c.added_on
FROM crop_catalog c
JOIN taxon t ON t.taxon_id = c.taxon_id
WHERE c.farm_id = %(farm_id)s
ORDER BY COALESCE(t.common_name, t.scientific_name)
"""

RECENT_EVENTS_SQL = """
SELECT e.event_id, e.event_date, k.label AS event_kind,
       COALESCE(t.common_name, t.scientific_name) AS crop,
       pl.name AS plot, e.quantity, e.unit
FROM farm_event e
JOIN event_kind k ON k.event_kind_code = e.event_kind_code
JOIN taxon t      ON t.taxon_id = e.taxon_id
LEFT JOIN plot pl ON pl.plot_id = e.plot_id
WHERE e.farm_id = %(farm_id)s
ORDER BY e.event_date DESC, e.event_id DESC
LIMIT 10
"""

# For each harvest, what the same crop sold for at auction within 30 days
# either side of the harvest date. Joins the event log, farm, event kind,
# taxonomy, product lexicon and market lots (through product_alias).
HARVEST_PRICES_SQL = """
SELECT f.name                             AS farm,
       e.event_date                       AS harvested_on,
       COALESCE(t.common_name, t.scientific_name) AS crop,
       e.quantity, e.unit,
       p.title                            AS market_product,
       COUNT(l.lot_id)                    AS lots_in_window,
       ROUND(AVG(l.avg_cents) / 100.0, 2) AS mean_price,
       MIN(l.low_cents)  / 100.0          AS low_price,
       MAX(l.high_cents) / 100.0          AS high_price
FROM farm_event e
JOIN farm f           ON f.farm_id = e.farm_id
JOIN event_kind k     ON k.event_kind_code = e.event_kind_code
                     AND k.is_yield
JOIN taxon t          ON t.taxon_id = e.taxon_id
JOIN product p        ON p.taxon_id = e.taxon_id
JOIN product_alias a  ON a.product_id = p.product_id
JOIN market_lot l     ON l.label_norm = a.label_norm
                     AND l.sale_date BETWEEN e.event_date - 30
                                         AND e.event_date + 30
WHERE e.farm_id = %(farm_id)s
GROUP BY f.name, e.event_id, e.event_date, t.common_name, t.scientific_name,
         e.quantity, e.unit, p.title
ORDER BY e.event_date DESC, lots_in_window DESC
"""


def load_farm(farm_id):
    """Return the farm row or stop the request with 404."""
    farm = query_one(FARM_SQL, {"farm_id": farm_id})
    if farm is None:
        abort(404)
    return farm


@bp.route("/")
def farm_list():
    term = request.args.get("q", "").strip()
    pattern = like_pattern(term) if term else None
    return render_template(
        "farms/list.html", term=term, farms=query(FARM_LIST_SQL, {"pattern": pattern})
    )


@bp.route("/new", methods=["GET", "POST"])
def farm_new():
    if request.method == "POST":
        try:
            values = {
                "name": forms.text(request.form, "name", "Farm name", 200, required=True),
                "domain": forms.text(request.form, "domain", "Web domain", 255),
                "owner_email": forms.text(request.form, "owner_email", "Owner email", 255),
                "region_id": forms.integer(request.form, "region_id", "County", required=True),
            }
            row = execute(INSERT_FARM_SQL, values)
            flash("Farm added.")
            return redirect(url_for("farms.farm_detail", farm_id=row["farm_id"]))
        except forms.FormError as err:
            flash(str(err), "error")
        except psycopg.Error as err:
            flash(errors.describe(err), "error")
    return render_template(
        "farms/new.html", regions=query(REGION_CHOICES_SQL), form=request.form
    )


@bp.route("/<int:farm_id>")
def farm_detail(farm_id):
    farm = load_farm(farm_id)
    params = {"farm_id": farm_id}
    return render_template(
        "farms/detail.html",
        farm=farm,
        plots=query(OVERVIEW_PLOTS_SQL, params),
        catalog=query(OVERVIEW_CATALOG_SQL, params),
        events=query(RECENT_EVENTS_SQL, params),
    )


@bp.route("/<int:farm_id>/harvest-prices")
def harvest_prices(farm_id):
    farm = load_farm(farm_id)
    return render_template(
        "farms/harvest_prices.html",
        farm=farm,
        rows=query(HARVEST_PRICES_SQL, {"farm_id": farm_id}),
    )
