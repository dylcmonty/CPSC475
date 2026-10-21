"""Insert, update and delete a farm's plots."""
import psycopg
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from . import errors, forms
from .db import execute, query_one
from .farms import load_farm

bp = Blueprint("plots", __name__, url_prefix="/farms/<int:farm_id>/plots")

PLOT_SQL = """
SELECT plot_id, name, area_sq_m
FROM plot
WHERE plot_id = %(plot_id)s AND farm_id = %(farm_id)s
"""

INSERT_PLOT_SQL = """
INSERT INTO plot (farm_id, name, area_sq_m)
VALUES (%(farm_id)s, %(name)s, %(area_sq_m)s)
RETURNING plot_id
"""

UPDATE_PLOT_SQL = """
UPDATE plot SET name = %(name)s, area_sq_m = %(area_sq_m)s
WHERE plot_id = %(plot_id)s AND farm_id = %(farm_id)s
"""

DELETE_PLOT_SQL = """
DELETE FROM plot
WHERE plot_id = %(plot_id)s AND farm_id = %(farm_id)s
"""


def read_plot_form(form):
    return {
        "name": forms.text(form, "name", "Plot name", 100, required=True),
        "area_sq_m": forms.decimal(form, "area_sq_m", "Area"),
    }


@bp.route("/new", methods=["GET", "POST"])
def plot_new(farm_id):
    farm = load_farm(farm_id)
    if request.method == "POST":
        try:
            execute(INSERT_PLOT_SQL, {"farm_id": farm_id, **read_plot_form(request.form)})
            flash("Plot added.")
            return redirect(url_for("farms.farm_detail", farm_id=farm_id))
        except forms.FormError as err:
            flash(str(err), "error")
        except psycopg.Error as err:
            flash(errors.describe(err), "error")
    return render_template("plots/form.html", farm=farm, plot=None, form=request.form)


@bp.route("/<int:plot_id>/edit", methods=["GET", "POST"])
def plot_edit(farm_id, plot_id):
    farm = load_farm(farm_id)
    plot = query_one(PLOT_SQL, {"farm_id": farm_id, "plot_id": plot_id})
    if plot is None:
        abort(404)
    if request.method == "POST":
        try:
            execute(UPDATE_PLOT_SQL,
                    {"farm_id": farm_id, "plot_id": plot_id, **read_plot_form(request.form)})
            flash("Plot updated.")
            return redirect(url_for("farms.farm_detail", farm_id=farm_id))
        except forms.FormError as err:
            flash(str(err), "error")
        except psycopg.Error as err:
            flash(errors.describe(err), "error")
    form = request.form if request.method == "POST" else plot
    return render_template("plots/form.html", farm=farm, plot=plot, form=form)


@bp.route("/<int:plot_id>/delete", methods=["POST"])
def plot_delete(farm_id, plot_id):
    deleted = execute(DELETE_PLOT_SQL, {"farm_id": farm_id, "plot_id": plot_id})
    if deleted:
        flash("Plot deleted. Its events were kept with no plot.")
    return redirect(url_for("farms.farm_detail", farm_id=farm_id))
