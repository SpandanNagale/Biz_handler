import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Local, offline SQLite database — a single file, no external service required.
# Lives in instance/ (Flask convention for local/instance-specific data, git-ignored).
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_SQLITE_PATH = INSTANCE_DIR / "coldrink.db"


class Config:
    SECRET_KEY = os.environ["SECRET_KEY"]

    # DATABASE_URL lets you point at something else if you ever need to (e.g. a shared
    # network drive's file, or a different DB entirely) — unset, it just uses the local file.
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or f"sqlite:///{DEFAULT_SQLITE_PATH}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
    ADMIN_PASSWORD_HASH = os.environ["ADMIN_PASSWORD_HASH"]

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") != "development"

    # A trip entry page can stay open for a whole route run (several hours) with
    # autosave quietly posting in the background. Flask-WTF's default CSRF token
    # lifetime is 1 hour, which would start rejecting those posts mid-route — so
    # it's extended to cover a full working day instead.
    WTF_CSRF_TIME_LIMIT = 28800

    # Fixed business timezone for "today" calculations (dashboard, defaults).
    BUSINESS_TIMEZONE = "Asia/Kolkata"
