import os
import sqlite3
from datetime import datetime

from flask import Flask, g, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "bet_league.db")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme")

MATCH_TYPE_LABELS = {
    "QF": "Quarterfinal",
    "SF": "Semifinal",
    "THIRD": "Third Place Playoff",
    "FINAL": "Final",
}

SEED_MATCHES = [
    ("QF", "France", "Morocco", 0.10, "2026-07-10T04:00", 1),
    ("QF", "Spain", "Belgium", 0.10, "2026-07-11T03:00", 2),
    ("QF", "Norway", "England", 0.10, "2026-07-12T05:00", 3),
    ("QF", "Argentina", "Switzerland", 0.10, "2026-07-12T09:00", 4),
    ("SF", "TBD", "TBD", 0.20, "2026-07-15T03:00", 5),
    ("SF", "TBD", "TBD", 0.20, "2026-07-16T03:00", 6),
    ("THIRD", "TBD", "TBD", 0.20, None, 7),
    ("FINAL", "TBD", "TBD", 1.00, None, 8),
]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS player (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            display_name TEXT NOT NULL,
            pin_hash TEXT NOT NULL,
            paid INTEGER NOT NULL DEFAULT 0,
            joined_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS match (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            team_a TEXT NOT NULL,
            team_b TEXT NOT NULL,
            stake_amount REAL NOT NULL,
            kickoff_at TEXT,
            winner TEXT,
            sort_order INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS pick (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL REFERENCES player(id),
            match_id INTEGER NOT NULL REFERENCES match(id),
            picked_winner TEXT NOT NULL,
            submitted_at TEXT NOT NULL,
            UNIQUE(player_id, match_id)
        );
        """
    )
    db.commit()

    count = db.execute("SELECT COUNT(*) FROM match").fetchone()[0]
    if count == 0:
        db.executemany(
            "INSERT INTO match (type, team_a, team_b, stake_amount, kickoff_at, sort_order) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            SEED_MATCHES,
        )
        db.commit()
    db.close()


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def parse_dt(value):
    if not value:
        return None
    return datetime.fromisoformat(value)


def match_is_open(match):
    kickoff = parse_dt(match["kickoff_at"])
    return kickoff is None or datetime.now() < kickoff


def match_status(match):
    if match["winner"]:
        return "settled"
    if match_is_open(match):
        return "open"
    return "locked"


def get_current_player():
    player_id = session.get("player_id")
    if not player_id:
        return None
    return get_db().execute("SELECT * FROM player WHERE id = ?", (player_id,)).fetchone()


def is_admin():
    return bool(session.get("is_admin"))


@app.context_processor
def inject_globals():
    return {"current_player": get_current_player(), "is_admin": is_admin()}


def compute_player_stats(db, player_id):
    picks = db.execute(
        """
        SELECT pick.picked_winner, match.id AS match_id, match.stake_amount,
               match.winner, match.type
        FROM pick JOIN match ON match.id = pick.match_id
        WHERE pick.player_id = ?
        """,
        (player_id,),
    ).fetchall()

    bets_placed = len(picks)
    stake_committed = sum(p["stake_amount"] for p in picks)
    settled = [p for p in picks if p["winner"]]
    correct = [p for p in settled if p["picked_winner"] == p["winner"]]
    accuracy = (len(correct) / len(settled) * 100) if settled else None

    winnings = 0.0
    for p in settled:
        pickers = db.execute(
            "SELECT picked_winner FROM pick WHERE match_id = ?", (p["match_id"],)
        ).fetchall()
        pot_total = p["stake_amount"] * len(pickers)
        correct_count = sum(1 for row in pickers if row["picked_winner"] == p["winner"])
        if p["picked_winner"] == p["winner"]:
            if correct_count > 0:
                winnings += pot_total / correct_count
        elif correct_count == 0:
            # nobody picked the actual winner for this match - refund everyone's stake
            winnings += p["stake_amount"]

    return {
        "bets_placed": bets_placed,
        "stake_committed": stake_committed,
        "accuracy": accuracy,
        "winnings": winnings,
    }


@app.route("/")
def leaderboard():
    db = get_db()
    players = db.execute("SELECT * FROM player ORDER BY joined_at").fetchall()
    rows = []
    for player in players:
        stats = compute_player_stats(db, player["id"])
        rows.append({"player": player, **stats})
    rows.sort(key=lambda r: r["winnings"], reverse=True)
    return render_template("leaderboard.html", rows=rows)


@app.route("/join", methods=["GET", "POST"])
def join():
    if request.method == "POST":
        name = request.form.get("display_name", "").strip()
        pin = request.form.get("pin", "").strip()

        if not name or not pin:
            flash("Enter a display name and a PIN.")
            return redirect(url_for("join"))
        if not pin.isdigit() or len(pin) != 4:
            flash("PIN must be exactly 4 digits.")
            return redirect(url_for("join"))

        db = get_db()
        existing = db.execute(
            "SELECT * FROM player WHERE display_name = ?", (name,)
        ).fetchone()

        if existing:
            if check_password_hash(existing["pin_hash"], pin):
                session["player_id"] = existing["id"]
                flash(f"Welcome back, {existing['display_name']}!")
                return redirect(url_for("picks"))
            else:
                # name taken by someone else - disambiguate with a suffix
                suffix = 2
                candidate = f"{name} ({suffix})"
                while db.execute(
                    "SELECT 1 FROM player WHERE display_name = ?", (candidate,)
                ).fetchone():
                    suffix += 1
                    candidate = f"{name} ({suffix})"
                name = candidate
                flash(f"That name was taken, so you've joined as '{name}'.")

        pin_hash = generate_password_hash(pin)
        cur = db.execute(
            "INSERT INTO player (display_name, pin_hash, paid, joined_at) VALUES (?, ?, 0, ?)",
            (name, pin_hash, now_iso()),
        )
        db.commit()
        session["player_id"] = cur.lastrowid
        flash(f"You're in, {name}! Go place your picks.")
        return redirect(url_for("picks"))

    return render_template("join.html")


@app.route("/logout")
def logout():
    session.pop("player_id", None)
    return redirect(url_for("leaderboard"))


@app.route("/picks", methods=["GET", "POST"])
def picks():
    player = get_current_player()
    if not player:
        flash("Join or log in first.")
        return redirect(url_for("join"))

    db = get_db()

    if request.method == "POST":
        matches = db.execute("SELECT * FROM match").fetchall()
        for match in matches:
            if not match_is_open(match):
                continue
            choice = request.form.get(f"match_{match['id']}")
            if choice not in (match["team_a"], match["team_b"]):
                continue
            existing_pick = db.execute(
                "SELECT * FROM pick WHERE player_id = ? AND match_id = ?",
                (player["id"], match["id"]),
            ).fetchone()
            if existing_pick:
                db.execute(
                    "UPDATE pick SET picked_winner = ?, submitted_at = ? WHERE id = ?",
                    (choice, now_iso(), existing_pick["id"]),
                )
            else:
                db.execute(
                    "INSERT INTO pick (player_id, match_id, picked_winner, submitted_at) "
                    "VALUES (?, ?, ?, ?)",
                    (player["id"], match["id"], choice, now_iso()),
                )
        db.commit()
        flash("Picks saved.")
        return redirect(url_for("picks"))

    matches = db.execute("SELECT * FROM match ORDER BY sort_order").fetchall()
    my_picks = {
        row["match_id"]: row["picked_winner"]
        for row in db.execute(
            "SELECT match_id, picked_winner FROM pick WHERE player_id = ?", (player["id"],)
        ).fetchall()
    }

    view_rows = []
    for match in matches:
        view_rows.append(
            {
                "match": match,
                "type_label": MATCH_TYPE_LABELS.get(match["type"], match["type"]),
                "status": match_status(match),
                "my_pick": my_picks.get(match["id"]),
            }
        )

    return render_template("picks.html", rows=view_rows)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Wrong admin password.")
        return redirect(url_for("admin_login"))
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("leaderboard"))


def require_admin():
    if not is_admin():
        flash("Admin login required.")
        return False
    return True


@app.route("/admin")
def admin_dashboard():
    if not require_admin():
        return redirect(url_for("admin_login"))

    db = get_db()
    matches = db.execute("SELECT * FROM match ORDER BY sort_order").fetchall()
    match_rows = []
    for match in matches:
        pickers = db.execute(
            "SELECT picked_winner FROM pick WHERE match_id = ?", (match["id"],)
        ).fetchall()
        pot_total = match["stake_amount"] * len(pickers)
        correct_count = sum(1 for p in pickers if p["picked_winner"] == match["winner"]) if match["winner"] else 0
        match_rows.append(
            {
                "match": match,
                "type_label": MATCH_TYPE_LABELS.get(match["type"], match["type"]),
                "status": match_status(match),
                "picks_count": len(pickers),
                "pot_total": pot_total,
                "correct_count": correct_count,
                "payout_each": (pot_total / correct_count) if correct_count else None,
            }
        )

    players = db.execute("SELECT * FROM player ORDER BY joined_at").fetchall()
    player_rows = []
    for player in players:
        stats = compute_player_stats(db, player["id"])
        player_rows.append({"player": player, **stats})

    return render_template("admin.html", match_rows=match_rows, player_rows=player_rows)


@app.route("/admin/matches/<int:match_id>/edit", methods=["POST"])
def admin_edit_match(match_id):
    if not require_admin():
        return redirect(url_for("admin_login"))
    db = get_db()
    team_a = request.form.get("team_a", "").strip()
    team_b = request.form.get("team_b", "").strip()
    kickoff_at = request.form.get("kickoff_at", "").strip()
    db.execute(
        "UPDATE match SET team_a = ?, team_b = ?, kickoff_at = ? WHERE id = ?",
        (team_a, team_b, kickoff_at or None, match_id),
    )
    db.commit()
    flash("Match updated.")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/matches/<int:match_id>/result", methods=["POST"])
def admin_set_result(match_id):
    if not require_admin():
        return redirect(url_for("admin_login"))
    db = get_db()
    winner = request.form.get("winner", "").strip()
    match = db.execute("SELECT * FROM match WHERE id = ?", (match_id,)).fetchone()
    if match and winner in (match["team_a"], match["team_b"]):
        db.execute("UPDATE match SET winner = ? WHERE id = ?", (winner, match_id))
        db.commit()
        flash("Result recorded.")
    else:
        flash("Winner must match one of the two teams.")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/matches/<int:match_id>/clear_result", methods=["POST"])
def admin_clear_result(match_id):
    if not require_admin():
        return redirect(url_for("admin_login"))
    db = get_db()
    db.execute("UPDATE match SET winner = NULL WHERE id = ?", (match_id,))
    db.commit()
    flash("Result cleared.")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/players/<int:player_id>/toggle_paid", methods=["POST"])
def admin_toggle_paid(player_id):
    if not require_admin():
        return redirect(url_for("admin_login"))
    db = get_db()
    player = db.execute("SELECT * FROM player WHERE id = ?", (player_id,)).fetchone()
    if player:
        db.execute(
            "UPDATE player SET paid = ? WHERE id = ?", (0 if player["paid"] else 1, player_id)
        )
        db.commit()
    return redirect(url_for("admin_dashboard"))


init_db()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
