
from flask import Flask, redirect, session, url_for, render_template, request
from flask_discord_interactions import DiscordOAuth2Session, requires_authorization
import os

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

app.config["DISCORD_CLIENT_ID"] = os.getenv("DISCORD_CLIENT_ID")
app.config["DISCORD_CLIENT_SECRET"] = os.getenv("DISCORD_CLIENT_SECRET")
app.config["DISCORD_REDIRECT_URI"] = "https://www.bosscape.com/callback"

discord = DiscordOAuth2Session(app)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login/")
def login():
    return discord.create_session()

@app.route("/callback/")
def callback():
    discord.callback()
    return redirect(url_for("dashboard"))

@app.route("/dashboard/")
@requires_authorization
def dashboard():
    user = discord.fetch_user()
    return render_template("dashboard.html", user=user)

@app.route("/logout/")
def logout():
    discord.revoke()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run()
