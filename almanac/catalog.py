"""Insert, update and delete entries in a farm's crop catalog."""
import psycopg
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from . import errors, forms
from .db import execute, query, query_one
from .farms import load_farm
from .main import CATALOG_SEARCH_SQL, like_pattern

bp = Blueprint("catalog", __name__, url_prefix="/farms/<int:farm_id>/catalog")

CATALOG_SQL = """
SELECT c.taxon_id, t.rank, t.common_name, t.scientific_name, c.added_on, c.notes,
       (SELECT COUNT(*) FROM farm_event e
        WHERE e.farm_id = c.farm_id AND e.taxon_id = c.taxon_id) AS events
FROM crop_catalog c
JOIN taxon t ON t.taxon_id = c.taxon_id
WHERE c.farm_id = %(farm_id)s
ORDER BY COALESCE(t.common_name, t.scientific_name)
"""

ENTRY_SQL = """
SELECT c.taxon_id, t.common_name, t.scientific_name, c.notes
FROM crop_catalog c
JOIN taxon t ON t.taxon_id = c.taxon_id
WHERE c.farm_id = %(farm_id)s AND c.taxon_id = %(taxon_id)s
"""

INSERT_ENTRY_SQL = """
INSERT INTO crop_catalog (farm_id, taxon_id, notes)
VALUES (%(farm_id)s, %(taxon_id)s, %(notes)s)
ON CONFLICT (farm_id, taxon_id) DO NOTHING
"""

UPDATE_ENTRY_SQL = """
UPDATE crop_catalog SET notes = %(notes)s
WHERE farm_id = %(farm_id)s AND taxon_id = %(taxon_id)s
"""

DELETE_ENTRY_SQL = """
DELETE FROM crop_catalog
WHERE farm_id = %(farm_id)s AND taxon_id = %(taxon_id)s
"""


@bp.route("/")
def catalog_list(farm_id):
    farm = load_farm(farm_id)
    term = request.args.get("q", "").strip()
    matches = query(CATALOG_SEARCH_SQL, {"pattern": like_pattern(term)}) if term else []
    return render_template(
        "catalog/list.html",
        farm=farm,
        entries=query(CATALOG_SQL, {"farm_id": farm_id}),
        term=term,
        matches=matches,
    )


@bp.route("/add", methods=["POST"])
def catalog_add(farm_id):
    load_farm(farm_id)
    try:
        values = {
            "farm_id": farm_id,
            "taxon_id": forms.integer(request.form, "taxon_id", "Crop", required=True),
            "notes": forms.text(request.form, "notes", "Notes", 500),
        }
        if execute(INSERT_ENTRY_SQL, values):
            flash("Crop added to the catalog.")
        else:
            flash("That crop is already in the catalog.")
    except forms.FormError as err:
        flash(str(err), "error")
    except psycopg.Error as err:
        flash(errors.describe(err), "error")
    return redirect(url_for("catalog.catalog_list", farm_id=farm_id))


@bp.route("/<int:taxon_id>/edit", methods=["GET", "POST"])
def catalog_edit(farm_id, taxon_id):
    farm = load_farm(farm_id)
    entry = query_one(ENTRY_SQL, {"farm_id": farm_id, "taxon_id": taxon_id})
    if entry is None:
        abort(404)
    if request.method == "POST":
        try:
            notes = forms.text(request.form, "notes", "Notes", 500)
            execute(UPDATE_ENTRY_SQL, {"farm_id": farm_id, "taxon_id": taxon_id, "notes": notes})
            flash("Catalog entry updated.")
            return redirect(url_for("catalog.catalog_list", farm_id=farm_id))
        except forms.FormError as err:
            flash(str(err), "error")
        except psycopg.Error as err:
            flash(errors.describe(err), "error")
    form = request.form if request.method == "POST" else entry
    return render_template("catalog/edit.html", farm=farm, entry=entry, form=form)


@bp.route("/<int:taxon_id>/delete", methods=["POST"])
def catalog_delete(farm_id, taxon_id):
    if execute(DELETE_ENTRY_SQL, {"farm_id": farm_id, "taxon_id": taxon_id}):
        flash("Crop removed from the catalog. Its recorded events were kept.")
    return redirect(url_for("catalog.catalog_list", farm_id=farm_id))
