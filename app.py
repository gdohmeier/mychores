import os
import re
import secrets
import sqlite3
from datetime import datetime

from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

APP_NAME = "mychores"
DB_PATH = os.environ.get("DB_PATH", "/data/mychores.db")
SECRET_KEY_FILE = os.environ.get("SECRET_KEY_FILE", "/data/secret_key")
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DEFAULT_COLORS = [
    "#2f6f4e", "#3d5a80", "#9b2226", "#7b2cbf",
    "#b5651d", "#0077b6", "#6d4c41", "#2a9d8f",
]
TITLE_MAX = 80
NAME_MAX = 40
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
HEX_DIGITS = set("0123456789abcdefABCDEF")


def load_secret_key():
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key
    directory = os.path.dirname(SECRET_KEY_FILE) or "."
    os.makedirs(directory, exist_ok=True)
    if os.path.exists(SECRET_KEY_FILE):
        with open(SECRET_KEY_FILE, "r", encoding="utf-8") as fh:
            key = fh.read().strip()
            if key:
                return key
    key = secrets.token_hex(32)
    fd = os.open(SECRET_KEY_FILE, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(key)
    return key


app = Flask(__name__)
app.secret_key = load_secret_key()
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024


def get_db():
    if "db" not in g:
        os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS kids (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            color TEXT NOT NULL DEFAULT '#2f6f4e'
        );
        CREATE TABLE IF NOT EXISTS chores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kid_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            day INTEGER NOT NULL CHECK(day BETWEEN 0 AND 6),
            time TEXT NOT NULL,
            done INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (kid_id) REFERENCES kids(id) ON DELETE CASCADE
        );
        """
    )
    cols = {row[1] for row in db.execute("PRAGMA table_info(kids)").fetchall()}
    if "color" not in cols:
        db.execute("ALTER TABLE kids ADD COLUMN color TEXT NOT NULL DEFAULT '#2f6f4e'")
    db.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_chores_unique
        ON chores (kid_id, lower(title), day, time)
        """
    )
    db.commit()


def csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def valid_color(value):
    return bool(value and COLOR_RE.match(value))


def normalize_title(value):
    return " ".join((value or "").split())[:TITLE_MAX]


def normalize_name(value):
    return " ".join((value or "").split())[:NAME_MAX]


def kid_exists(kid_id):
    if not kid_id:
        return False
    row = get_db().execute("SELECT id FROM kids WHERE id = ?", (kid_id,)).fetchone()
    return row is not None


@app.before_request
def before_request():
    init_db()
    if request.method == "POST":
        token = request.form.get("csrf_token", "")
        if not token or not secrets.compare_digest(token, session.get("csrf_token", "")):
            return "Forbidden", 403


@app.context_processor
def inject_csrf():
    return {"csrf_token": csrf_token, "app_name": APP_NAME, "days": DAYS}


@app.get("/up")
def up():
    return "OK", 200


@app.get("/")
def index():
    db = get_db()
    kids = db.execute("SELECT * FROM kids ORDER BY name COLLATE NOCASE").fetchall()
    selected = request.args.get("kid", type=int)
    if selected is not None and not kid_exists(selected):
        selected = None
    if selected is None and kids:
        selected = kids[0]["id"]

    selected_kid = None
    chores_by_day = {i: [] for i in range(7)}
    if selected:
        selected_kid = db.execute("SELECT * FROM kids WHERE id = ?", (selected,)).fetchone()
        rows = db.execute(
            """
            SELECT * FROM chores
            WHERE kid_id = ?
            ORDER BY time, title COLLATE NOCASE
            """,
            (selected,),
        ).fetchall()
        for row in rows:
            chores_by_day[row["day"]].append(row)

    return render_template(
        "index.html",
        kids=kids,
        selected=selected,
        selected_kid=selected_kid,
        chores_by_day=chores_by_day,
        today=datetime.now().weekday(),
        default_colors=DEFAULT_COLORS,
    )


@app.post("/kids")
def add_kid():
    name = normalize_name(request.form.get("name"))
    color = request.form.get("color", DEFAULT_COLORS[0])
    if not valid_color(color):
        color = DEFAULT_COLORS[0]
    if not name:
        flash("Enter a kid name.")
        return redirect(url_for("index"))
    db = get_db()
    existing = db.execute(
        "SELECT id FROM kids WHERE lower(name) = lower(?)",
        (name,),
    ).fetchone()
    if existing:
        flash("That kid is already on the board.")
        return redirect(url_for("index", kid=existing["id"]))
    db.execute("INSERT INTO kids (name, color) VALUES (?, ?)", (name, color.lower()))
    db.commit()
    kid_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    return redirect(url_for("index", kid=kid_id))


@app.post("/kids/<int:kid_id>/color")
def update_kid_color(kid_id):
    color = request.form.get("color", "")
    if not kid_exists(kid_id):
        return redirect(url_for("index"))
    if not valid_color(color):
        flash("Pick a valid color.")
        return redirect(url_for("index", kid=kid_id))
    db = get_db()
    db.execute("UPDATE kids SET color = ? WHERE id = ?", (color.lower(), kid_id))
    db.commit()
    return redirect(url_for("index", kid=kid_id))


@app.post("/kids/<int:kid_id>/delete")
def delete_kid(kid_id):
    db = get_db()
    db.execute("DELETE FROM kids WHERE id = ?", (kid_id,))
    db.commit()
    return redirect(url_for("index"))


@app.post("/chores")
def add_chore():
    kid_id = request.form.get("kid_id", type=int)
    title = normalize_title(request.form.get("title"))
    time = (request.form.get("time") or "").strip()
    raw_days = request.form.getlist("day")
    parsed_days = []
    for item in raw_days:
        try:
            day = int(item)
        except (TypeError, ValueError):
            continue
        if 0 <= day <= 6:
            parsed_days.append(day)
    parsed_days = sorted(set(parsed_days))

    if not kid_exists(kid_id):
        flash("Select a kid first.")
        return redirect(url_for("index"))
    if not title or not TIME_RE.match(time) or not parsed_days:
        flash("Add a title, a valid time, and at least one day.")
        return redirect(url_for("index", kid=kid_id))

    db = get_db()
    added = 0
    skipped = 0
    for day in parsed_days:
        try:
            db.execute(
                "INSERT INTO chores (kid_id, title, day, time, done) VALUES (?, ?, ?, ?, 0)",
                (kid_id, title, day, time),
            )
            added += 1
        except sqlite3.IntegrityError:
            skipped += 1
    db.commit()

    if added and skipped:
        flash(f"Added to {added} day(s). Skipped {skipped} duplicate day(s).")
    elif skipped and not added:
        flash("That chore already exists on the selected day(s).")
    return redirect(url_for("index", kid=kid_id))


@app.post("/chores/<int:chore_id>/toggle")
def toggle_chore(chore_id):
    db = get_db()
    row = db.execute("SELECT kid_id, done FROM chores WHERE id = ?", (chore_id,)).fetchone()
    if not row:
        return redirect(url_for("index"))
    db.execute("UPDATE chores SET done = ? WHERE id = ?", (0 if row["done"] else 1, chore_id))
    db.commit()
    return redirect(url_for("index", kid=row["kid_id"]))


@app.post("/chores/<int:chore_id>/delete")
def delete_chore(chore_id):
    db = get_db()
    row = db.execute("SELECT kid_id FROM chores WHERE id = ?", (chore_id,)).fetchone()
    if row:
        db.execute("DELETE FROM chores WHERE id = ?", (chore_id,))
        db.commit()
        return redirect(url_for("index", kid=row["kid_id"]))
    return redirect(url_for("index"))


@app.post("/kids/<int:kid_id>/reset")
def reset_week(kid_id):
    if not kid_exists(kid_id):
        return redirect(url_for("index"))
    db = get_db()
    db.execute("UPDATE chores SET done = 0 WHERE kid_id = ?", (kid_id,))
    db.commit()
    return redirect(url_for("index", kid=kid_id))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
