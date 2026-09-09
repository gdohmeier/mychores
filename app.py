import os
import sqlite3
from datetime import datetime
from flask import Flask, g, redirect, render_template, request, url_for

APP_NAME = "mychores"
DB_PATH = os.environ.get("DB_PATH", "/data/mychores.db")
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

app = Flask(__name__)


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
            name TEXT NOT NULL
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
    db.commit()


@app.before_request
def before_request():
    init_db()


@app.get("/up")
def up():
    return "OK", 200


@app.get("/")
def index():
    db = get_db()
    kids = db.execute("SELECT * FROM kids ORDER BY name COLLATE NOCASE").fetchall()
    selected = request.args.get("kid", type=int)
    if selected is None and kids:
        selected = kids[0]["id"]

    chores_by_day = {i: [] for i in range(7)}
    if selected:
        rows = db.execute(
            """
            SELECT * FROM chores
            WHERE kid_id = ?
            ORDER BY time, title
            """,
            (selected,),
        ).fetchall()
        for row in rows:
            chores_by_day[row["day"]].append(row)

    return render_template(
        "index.html",
        app_name=APP_NAME,
        kids=kids,
        selected=selected,
        days=DAYS,
        chores_by_day=chores_by_day,
        today=datetime.now().weekday(),
    )


@app.post("/kids")
def add_kid():
    name = (request.form.get("name") or "").strip()
    if name:
        db = get_db()
        db.execute("INSERT INTO kids (name) VALUES (?)", (name,))
        db.commit()
        kid_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        return redirect(url_for("index", kid=kid_id))
    return redirect(url_for("index"))


@app.post("/kids/<int:kid_id>/delete")
def delete_kid(kid_id):
    db = get_db()
    db.execute("DELETE FROM kids WHERE id = ?", (kid_id,))
    db.commit()
    return redirect(url_for("index"))


@app.post("/chores")
def add_chore():
    kid_id = request.form.get("kid_id", type=int)
    title = (request.form.get("title") or "").strip()
    time = (request.form.get("time") or "").strip()
    days = request.form.getlist("day")
    parsed_days = []
    for d in days:
        try:
            n = int(d)
        except (TypeError, ValueError):
            continue
        if 0 <= n <= 6:
            parsed_days.append(n)
    parsed_days = sorted(set(parsed_days))

    if kid_id and title and time and parsed_days:
        db = get_db()
        db.executemany(
            "INSERT INTO chores (kid_id, title, day, time, done) VALUES (?, ?, ?, ?, 0)",
            [(kid_id, title, day, time) for day in parsed_days],
        )
        db.commit()
    return redirect(url_for("index", kid=kid_id))


@app.post("/chores/<int:chore_id>/toggle")
def toggle_chore(chore_id):
    db = get_db()
    row = db.execute("SELECT kid_id, done FROM chores WHERE id = ?", (chore_id,)).fetchone()
    if row:
        db.execute("UPDATE chores SET done = ? WHERE id = ?", (0 if row["done"] else 1, chore_id))
        db.commit()
        return redirect(url_for("index", kid=row["kid_id"]))
    return redirect(url_for("index"))


@app.post("/chores/<int:chore_id>/delete")
def delete_chore(chore_id):
    db = get_db()
    row = db.execute("SELECT kid_id FROM chores WHERE id = ?", (chore_id,)).fetchone()
    db.execute("DELETE FROM chores WHERE id = ?", (chore_id,))
    db.commit()
    return redirect(url_for("index", kid=row["kid_id"] if row else None))


@app.post("/kids/<int:kid_id>/reset")
def reset_week(kid_id):
    db = get_db()
    db.execute("UPDATE chores SET done = 0 WHERE kid_id = ?", (kid_id,))
    db.commit()
    return redirect(url_for("index", kid=kid_id))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

