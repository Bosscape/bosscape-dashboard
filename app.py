from flask import Flask, redirect, url_for, session, render_template, request
from flask_discord import DiscordOAuth2Session, requires_authorization, Unauthorized
import os
import socket
import traceback

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-me")

# Discord OAuth2 config
app.config["DISCORD_CLIENT_ID"] = os.getenv("DISCORD_CLIENT_ID")
app.config["DISCORD_CLIENT_SECRET"] = os.getenv("DISCORD_CLIENT_SECRET")
app.config["DISCORD_REDIRECT_URI"] = "http://127.0.0.1:5000/callback"  # Match your live site
app.config["DISCORD_SCOPE"] = ["identify"]

discord = DiscordOAuth2Session(app)

# Home page
@app.route("/")
def index():
    return render_template("index.html")

# Start Discord login
@app.route("/login/")
def login():
    return discord.create_session()

# OAuth2 callback handler
@app.route("/callback/")
def callback():
    print("DISCORD CALLBACK HIT")
    try:
        discord.callback()
        user = discord.fetch_user()
        print(f"Logged in user: {user.name} ({user.id})")
    except Exception as e:
        traceback.print_exc()  # this prints full traceback to terminal
        print("ERROR DURING DISCORD CALLBACK:", e)
        return "An error occurred during login.", 500

    return redirect(url_for("dashboard"))

# Protected dashboard (requires login)
@app.route("/dashboard/")
@requires_authorization
def dashboard():
    user = discord.fetch_user()
    return render_template("dashboard.html", user=user)

# Log out of Discord
@app.route("/logout/")
def logout():
    discord.revoke()
    return redirect(url_for("index"))

# Handle unauthorized access by redirecting to login
@app.errorhandler(Unauthorized)
def redirect_unauthorized(e):
    return redirect(url_for("login"))

# Local testing route (only if running locally)
@app.route("/simulate-login")
def simulate_login():
    if not request.host.startswith("127.0.0.1") and not request.host.startswith("localhost"):
        return "Simulated login only allowed locally", 403

    session["discord_user"] = "bosscape.official#0"
    return redirect(url_for("dashboard"))

# Temporary in-memory storage
user_rsn_map = {}

@app.route("/link", methods=["GET", "POST"])
def link_rsn():
    if request.method == "POST":
        rsn = request.form.get("rsn")
        user = discord.fetch_user()

        if not user:
            return "You must be logged in with Discord.", 401

        # Verify RSN via OSRS Hiscores
        hs_url = f"https://secure.runescape.com/m=hiscore_oldschool/index_lite.ws?player={rsn}"
        response = requests.get(hs_url)

        if response.status_code == 200:
            user_rsn_map[user.id] = rsn
            return redirect(url_for("view_stats"))
        else:
            return render_template("link.html", error="RSN not found or invalid.")

    return render_template("link.html")

@app.route("/stats")
@requires_authorization
def view_stats():
    user = discord.fetch_user()
    rsn = user_rsn_map.get(user.id)

    if not rsn:
        return redirect(url_for("link_rsn"))

    hs_url = f"https://secure.runescape.com/m=hiscore_oldschool/index_lite.ws?player={rsn}"
    response = requests.get(hs_url)
    stats = response.text.splitlines() if response.status_code == 200 else []

    # Basic stats parsing
    parsed = {
        "Attack XP": stats[0].split(",")[2] if len(stats) > 0 else "N/A",
        "Defence XP": stats[1].split(",")[2] if len(stats) > 1 else "N/A",
        "Total Level": stats[0].split(",")[1] if len(stats) > 0 else "N/A",
    }

    return render_template("stats.html", rsn=rsn, stats=parsed)


if __name__ == "__main__":
    app.run(debug=True)
