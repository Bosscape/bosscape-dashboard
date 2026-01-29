from flask import Flask, redirect, url_for, session, render_template, request
from flask_discord import DiscordOAuth2Session, Unauthorized
from db import SessionLocal
from models import User
from routes.queue import bp as queue_bp
from auth import requires_login
import os
import traceback
import requests
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-me")

# ---------------- Discord OAuth ----------------
app.config["DISCORD_CLIENT_ID"] = os.getenv("DISCORD_CLIENT_ID")
app.config["DISCORD_CLIENT_SECRET"] = os.getenv("DISCORD_CLIENT_SECRET")
app.config["DISCORD_REDIRECT_URI"] = os.getenv("DISCORD_REDIRECT_URI")
app.config["DISCORD_SCOPE"] = ["identify"]

discord = DiscordOAuth2Session(app)
app.discord = discord  # 🔑 expose to blueprints safely

# ---------------- Blueprints ----------------
app.register_blueprint(queue_bp)

# ---------------- Routes ----------------

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login/")
def login():
    return discord.create_session()

@app.route("/callback/")
def callback():
    try:
        discord.callback()
        user = discord.fetch_user()
        print(f"Logged in: {user.name} ({user.id})")
    except Exception:
        traceback.print_exc()
        return "An error occurred during login.", 500

    return redirect(url_for("dashboard"))

@app.route("/dashboard/")
@requires_login
def dashboard():
    user = discord.fetch_user()
    return render_template("dashboard.html", user=user)

@app.route("/logout/")
def logout():
    discord.revoke()
    return redirect(url_for("index"))

@app.errorhandler(Unauthorized)
def redirect_unauthorized(e):
    return redirect(url_for("login"))

# ---------------- RSN Linking ----------------

@app.route("/link", methods=["GET", "POST"])
@requires_login
def link_rsn():
    if request.method == "POST":
        rsn = request.form.get("rsn")
        user = discord.fetch_user()

        hs_url = f"https://secure.runescape.com/m=hiscore_oldschool/index_lite.ws?player={rsn}"
        response = requests.get(hs_url)

        if response.status_code == 200:
            db = SessionLocal()
            try:
                existing = db.query(User).filter_by(discord_id=str(user.id)).first()
                if existing:
                    existing.rsn = rsn
                else:
                    db.add(User(discord_id=str(user.id), rsn=rsn))
                db.commit()
            finally:
                db.close()

            return redirect(url_for("view_stats"))

        return render_template("link.html", error="RSN not found or invalid.")

    return render_template("link.html")

# ---------------- Stats ----------------

@app.route("/stats")
@requires_login
def view_stats():
    # If ?rsn=Someone is passed in the URL, view their stats
    target_rsn = request.args.get("rsn")
    
    if target_rsn:
        rsn = target_rsn
    else:
        # Otherwise, fall back to the logged-in user's linked RSN
        user = discord.fetch_user()
        db = SessionLocal()
        try:
            user_entry = db.query(User).filter_by(discord_id=str(user.id)).first()
            if not user_entry:
                return redirect(url_for("link_rsn"))
            rsn = user_entry.rsn
        finally:
            db.close()

    hs_url = f"https://secure.runescape.com/m=hiscore_oldschool/index_lite.ws?player={rsn}"
    response = requests.get(hs_url)

    if response.status_code != 200:
        return "Error fetching stats.", 500

    lines = response.text.splitlines()
    parsed_stats = {}

    skill_names = [
        "Overall", "Attack", "Defence", "Strength", "Hitpoints", "Ranged",
        "Prayer", "Magic", "Cooking", "Woodcutting", "Fletching", "Fishing",
        "Firemaking", "Crafting", "Smithing", "Mining", "Herblore", "Agility",
        "Thieving", "Slayer", "Farming", "Runecraft", "Hunter", "Construction"
    ]

    for i, skill in enumerate(skill_names):
        try:
            rank, level, xp = lines[i].split(",")
            parsed_stats[skill] = {"level": level, "xp": xp, "rank": rank}
        except:
            parsed_stats[skill] = {"level": "N/A", "xp": "N/A", "rank": "N/A"}

    parsed_stats["Combat Level"] = combat_level(parsed_stats)
    return render_template("stats.html", rsn=rsn, stats=parsed_stats)

def combat_level(stats):
    try:
        attack = int(stats["Attack"]["level"])
        strength = int(stats["Strength"]["level"])
        defence = int(stats["Defence"]["level"])
        hitpoints = int(stats["Hitpoints"]["level"])
        prayer = int(stats["Prayer"]["level"])
        ranged = int(stats["Ranged"]["level"])
        magic = int(stats["Magic"]["level"])

        base = 0.25 * (defence + hitpoints + (prayer // 2))
        melee = 0.325 * (attack + strength)
        range = 0.325 * (ranged * 1.5)
        mage = 0.325 * (magic * 1.5)

        return round(base + max(melee, range, mage), 2)
    except:
        return "N/A"

@app.context_processor
def inject_now():
    return {"now": lambda: datetime.utcnow()}

if __name__ == "__main__":
    app.run(debug=True)