# auth.py

from flask import redirect, url_for, current_app
from functools import wraps

def requires_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        discord = current_app.discord
        if not discord.authorized:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function