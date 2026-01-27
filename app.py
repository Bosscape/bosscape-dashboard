from flask import Flask, redirect, url_for, session, render_template
from flask_discord import DiscordOAuth2Session, requires_authorization, Unauthorized
import os
import socket

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# Discord OAuth2 config
app.config["DISCORD_CLIENT_ID"] = os.getenv("DISCORD_CLIENT_ID")
app.config["DISCORD_CLIENT_SECRET"] = os.getenv("DISCORD_CLIENT_SECRET")
app.config["DISCORD_REDIRECT_URI"] = "https://bosscape.com/callback"  # Match your live site
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
        print("ERROR DURING DISCORD CALLBACK:", e)
        raise

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

if __name__ == "__main__":
    app.run(debug=True)
