"""Booking app: pick a slot, leave name + email, get a confirmation email."""
import hmac
import logging
import os
from datetime import datetime, timedelta
from html import escape

import psycopg
import requests
from flask import Flask, Response, render_template, request

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("booking")
app = Flask(__name__)

# Opening hours: Monday to Friday, one slot per hour, for the next 14 days.
DAYS_AHEAD = 14
FIRST_HOUR = 9
LAST_HOUR = 16  # last slot starts at 16:00
BUSINESS_NAME = os.environ.get("BUSINESS_NAME", "Book a time")

SCHEMA = """
CREATE TABLE IF NOT EXISTS bookings (
    id SERIAL PRIMARY KEY,
    slot TIMESTAMP NOT NULL UNIQUE,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""

_db_ready = False
_db_error = None


def ensure_db():
    """Create tables once. Returns True when the database is usable."""
    global _db_ready, _db_error
    if _db_ready:
        return True
    url = os.environ.get("DATABASE_URL")
    if not url:
        return False
    try:
        with psycopg.connect(url, connect_timeout=10) as conn:
            conn.execute(SCHEMA)
        _db_ready, _db_error = True, None
    except Exception as exc:  # keep the app alive, show a message instead
        _db_error = str(exc)
        log.exception("Database setup failed")
    return _db_ready


def connect():
    return psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=10)


def send_mail(to, subject, html):
    key = os.environ.get("CMO_MAIL_API_KEY")
    url = os.environ.get("CMO_MAIL_URL")
    sender = os.environ.get("MAIL_FROM")
    if not (key and url and sender):
        log.info("Mail not configured (need CMO_MAIL_API_KEY, CMO_MAIL_URL, MAIL_FROM); skipping email to %s", to)
        return False
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {key}"},
            json={"from": sender, "to": [to], "subject": subject, "html": html},
            timeout=10,
        )
        if not resp.ok:
            log.warning("Mail API answered %s: %s", resp.status_code, resp.text[:200])
        return resp.ok
    except Exception:
        log.exception("Could not send email")
        return False


def all_slots():
    now = datetime.now()
    slots = []
    for offset in range(DAYS_AHEAD + 1):
        day = (now + timedelta(days=offset)).replace(minute=0, second=0, microsecond=0)
        if day.weekday() >= 5:
            continue
        for hour in range(FIRST_HOUR, LAST_HOUR + 1):
            slot = day.replace(hour=hour)
            if slot > now + timedelta(hours=1):
                slots.append(slot)
    return slots


def free_slots():
    with connect() as conn:
        taken = {r[0] for r in conn.execute("SELECT slot FROM bookings WHERE slot >= now() - interval '1 day'")}
    days = {}
    for slot in all_slots():
        if slot not in taken:
            days.setdefault(slot.strftime("%A %d %B"), []).append(slot)
    return days


@app.before_request
def need_database():
    if request.endpoint == "static":
        return None
    if not ensure_db():
        return render_template("setup.html", site_name=BUSINESS_NAME, error=_db_error,
                               has_url=bool(os.environ.get("DATABASE_URL"))), (200 if request.method == "GET" else 503)
    return None


@app.get("/")
def index():
    return render_template("index.html", site_name=BUSINESS_NAME, days=free_slots(), error=None, form={})


@app.post("/book")
def book():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    slot_raw = request.form.get("slot", "")
    form = {"name": name, "email": email}

    def again(error):
        return render_template("index.html", site_name=BUSINESS_NAME, days=free_slots(), error=error, form=form), 400

    try:
        slot = datetime.strptime(slot_raw, "%Y-%m-%d %H:%M")
    except ValueError:
        return again("Please pick a time.")
    if slot not in all_slots():
        return again("That time is not available.")
    if not name or "@" not in email or len(name) > 200 or len(email) > 254:
        return again("Please enter your name and a valid email.")

    with connect() as conn:
        row = conn.execute(
            "INSERT INTO bookings (slot, name, email) VALUES (%s, %s, %s) "
            "ON CONFLICT (slot) DO NOTHING RETURNING id",
            (slot, name, email),
        ).fetchone()
    if row is None:
        return again("Sorry, someone just took that time. Please pick another.")

    when = slot.strftime("%A %d %B %Y at %H:%M")
    send_mail(
        email,
        f"Your booking: {when}",
        f"<p>Hi {escape(name)},</p><p>Your booking with {escape(BUSINESS_NAME)} is confirmed for "
        f"<strong>{escape(when)}</strong>.</p><p>If you need to change it, just reply to this email.</p>",
    )
    owner = os.environ.get("OWNER_EMAIL")
    if owner:
        send_mail(owner, f"New booking: {when}", f"<p>{escape(name)} ({escape(email)}) booked {escape(when)}.</p>")
    return render_template("done.html", site_name=BUSINESS_NAME, when=when, email=email)


def admin_ok():
    password = os.environ.get("ADMIN_PASSWORD")
    auth = request.authorization
    return bool(password and auth and hmac.compare_digest((auth.password or "").encode(), password.encode()))


@app.get("/admin")
def admin():
    if not os.environ.get("ADMIN_PASSWORD"):
        return render_template("admin_off.html", site_name=BUSINESS_NAME)
    if not admin_ok():
        return Response("Password required.", 401, {"WWW-Authenticate": 'Basic realm="Admin"'})
    with connect() as conn:
        rows = conn.execute("SELECT slot, name, email, created_at FROM bookings ORDER BY slot").fetchall()
    return render_template("admin.html", site_name=BUSINESS_NAME, rows=rows)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
