import os


class Config:
    SECRET_KEY = os.environ["SECRET_KEY"]

    # Runtime DB connection — Supabase transaction-mode pooler (port 6543).
    # Small/no pool since each serverless invocation is effectively a fresh process.
    SQLALCHEMY_DATABASE_URI = os.environ["DATABASE_URL"]
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 1,
        "max_overflow": 0,
        "pool_pre_ping": True,
        "pool_recycle": 180,
        "connect_args": {"options": "-c statement_timeout=10000"},
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
    ADMIN_PASSWORD_HASH = os.environ["ADMIN_PASSWORD_HASH"]

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") != "development"

    # Fixed business timezone for "today" calculations (dashboard, defaults).
    BUSINESS_TIMEZONE = "Asia/Kolkata"
