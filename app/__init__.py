import decimal
import json
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, redirect, request, url_for
from flask.json.provider import DefaultJSONProvider
from flask_login import current_user

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class DecimalJSONProvider(DefaultJSONProvider):
    """Serialize Decimal as string so trip-entry AJAX responses don't crash."""

    @staticmethod
    def default(obj):
        if isinstance(obj, decimal.Decimal):
            return str(obj)
        return DefaultJSONProvider.default(obj)


def create_app(config_object="app.config.Config"):
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )
    app.config.from_object(config_object)
    app.json_provider_class = DecimalJSONProvider
    app.json = DecimalJSONProvider(app)

    from app.extensions import csrf, db, limiter, login_manager, migrate

    db.init_app(app)

    # SQLite doesn't enforce FOREIGN KEY constraints unless told to per-connection.
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
        from sqlalchemy import event
        from sqlalchemy.engine import Engine

        @event.listens_for(Engine, "connect")
        def _enable_sqlite_fk(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    migrate.init_app(app, db, render_as_batch=True)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    limiter.init_app(app)
    csrf.init_app(app)

    from app.auth import auth_bp
    from app.production import production_bp
    from app.products import products_bp
    from app.reports import reports_bp
    from app.routes_bp import routes_bp
    from app.stores import stores_bp
    from app.trips import trips_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(production_bp)
    app.register_blueprint(routes_bp)
    app.register_blueprint(stores_bp)
    app.register_blueprint(trips_bp)
    app.register_blueprint(reports_bp)

    @app.before_request
    def require_login():
        if request.endpoint in (None, "auth.login", "static"):
            return
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login", next=request.path))

    return app
