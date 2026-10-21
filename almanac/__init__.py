"""Almanac: a taxonomy-linked farm record book with historical market pricing."""
import os

from flask import Flask

from . import db


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE_URL=os.environ.get("DATABASE_URL", "postgresql:///almanac"),
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev"),
    )
    if config:
        app.config.update(config)

    db.init_app(app)
    app.jinja_env.filters["blank"] = lambda value: "" if value is None else value
    app.jinja_env.filters["money"] = lambda value: "" if value is None else f"${value:,.2f}"

    from . import catalog, events, farms, main, plots

    app.register_blueprint(main.bp)
    app.register_blueprint(farms.bp)
    app.register_blueprint(plots.bp)
    app.register_blueprint(catalog.bp)
    app.register_blueprint(events.bp)

    return app
