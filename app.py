
from flask import Flask, redirect, url_for, session, render_template
from flask_discord import DiscordOAuth2Session, requires_authorization, Unauthorized
import os

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

app.config["DISCORD_CLIENT_ID"] = os.getenv("DISCORD_CLIENT_ID")
app.config["DISCORD_CLIENT_SECRET"] = os.getenv("DISCORD_CLIENT_SECRET")
app.config["DISCORD_REDIRECT_URI"] = "https://bosscape.onrender.com/callback"
app.config["DISCORD_SCOPE"] = ["identify"]

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

@app.errorhandler(Unauthorized)
def redirect_unauthorized(e):
    return redirect(url_for("login"))
