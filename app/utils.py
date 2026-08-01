from datetime import datetime
from zoneinfo import ZoneInfo

from flask import current_app


def business_today():
    """"Today" in the business's fixed timezone, not the server's (Vercel runs UTC)."""
    tz = ZoneInfo(current_app.config["BUSINESS_TIMEZONE"])
    return datetime.now(tz).date()
