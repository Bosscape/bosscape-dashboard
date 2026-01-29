from flask import Blueprint, render_template, request, redirect, url_for, current_app
from db import SessionLocal
from models import Queue, User, QueueMember
from datetime import datetime, timedelta
from auth import requires_login
from flask import flash
from sqlalchemy import desc
from sqlalchemy.orm import joinedload
import json
import traceback

bp = Blueprint("queue", __name__)

@bp.route("/queue/create", methods=["GET", "POST"])
@requires_login
def create_queue():
    discord = current_app.discord
    user = discord.fetch_user()

    RAIDS = sorted(["ToA", "ToB", "CoX"])
    BOSSES = sorted([
        "Callisto", "Chaos Elemental", "Corporeal", "Dagannoth Kings", "Giant Mole",
        "Graardor", "Hueycoatl", "Kalphite Queen", "King Black Dragon", "Kree'arra", "K'ril",
        "Nex", "Nightmare", "Sarachnis", "Scorpia", "Scurrius", "Tempoross", "Venenatis",
        "Wintertodt", "Yama", "Zalcano", "Zilyana"
    ])
    EVENT = ["Event"]

    if request.method == "POST":
        category = request.form.get("category")
        activity = request.form.get("activity")
        role = request.form.get("role")
        group_size = int(request.form.get("group_size"))
        expires_in = min(int(request.form.get("expires_in", 60)), 180)
        notes = request.form.get("notes", "")
        flash("Queue created successfully!")

        db = SessionLocal()
        try:
            creator = db.query(User).filter_by(discord_id=str(user.id)).first()
            if not creator:
                return redirect(url_for("link_rsn"))

            queue = Queue(
                boss=activity,
                role=role,
                group_size=max(2, min(group_size, 100)),
                created_by=str(user.id),
                description=notes,
                expires_at=datetime.utcnow() + timedelta(minutes=expires_in)
            )
            db.add(queue)
            db.commit() # Commit first

            # Add creator as member
            member = QueueMember(
                queue_id=queue.id,
                discord_id=str(user.id),
                rsn=creator.rsn
            )
            db.add(member)
            db.commit()
        finally:
            db.close()

        return redirect(url_for("queue.list_queues"))

    return render_template(
        "queue/create.html",
        raids=RAIDS,
        bosses=BOSSES,
        events=EVENT
    )

@bp.route("/queue/active")
@requires_login
def list_queues():
    discord = current_app.discord
    user = discord.fetch_user()
    db = SessionLocal()

    try:
        now_time = datetime.utcnow()
        queues = db.query(Queue).options(joinedload(Queue.members)).filter(Queue.expires_at > now_time).order_by(Queue.created_at.desc()).all()

        # Fetch RSNs for queue creators
        creator_ids = [q.created_by for q in queues]
        creators = db.query(User).filter(User.discord_id.in_(creator_ids)).all()
        creator_map = {u.discord_id: u.rsn for u in creators}

        queue_data = []
        for q in queues:
            queue_data.append({
                "id": q.id,
                "boss": q.boss,
                "role": q.role,
                "group_size": q.group_size,
                "expires_at": q.expires_at,
                "description": q.description,
                "members": [{"rsn": m.rsn, "discord_id": m.discord_id} for m in q.members],
                "host_rsn": creator_map.get(q.created_by, "Unknown")
            })

        return render_template("queue/active.html", queues=queue_data, current_user_id=str(user.id))

    except Exception as e:
        print("CRITICAL ERROR IN LIST_QUEUES:")
        traceback.print_exc()
        return f"CRITICAL ERROR: {str(e)} <br><pre>{traceback.format_exc()}</pre>", 500
    finally:
        db.close()

@bp.route("/queue/join/<int:queue_id>")
@requires_login
def join_queue(queue_id):
    user = current_app.discord.fetch_user()
    db = SessionLocal()
    try:
        queue = db.query(Queue).filter_by(id=queue_id).first()
        rsn_user = db.query(User).filter_by(discord_id=str(user.id)).first()
        
        if not queue:
            flash("Queue not found.", "error")
            return redirect(url_for("queue.list_queues"))
            
        if queue.expires_at < datetime.utcnow():
            flash("Queue expired.", "error")
            return redirect(url_for("queue.list_queues"))
            
        if not rsn_user:
             flash("Please link your RSN first.", "error")
             return redirect(url_for("link_rsn"))

        # Check if already joined
        existing = db.query(QueueMember).filter_by(queue_id=queue.id, discord_id=str(user.id)).first()
        if existing:
            flash("You are already in this queue.", "info")
            return redirect(url_for("queue.list_queues"))
            
        # Check if full
        if len(queue.members) >= queue.group_size:
            flash("Queue is full.", "error")
            return redirect(url_for("queue.list_queues"))
            
        # Join
        member = QueueMember(
            queue_id=queue.id,
            discord_id=str(user.id),
            rsn=rsn_user.rsn
        )
        db.add(member)
        db.commit()
        flash("Joined queue!", "success")
    finally:
        db.close()
    
    return redirect(url_for("queue.list_queues"))

@bp.route("/queue/leave/<int:queue_id>")
@requires_login
def leave_queue(queue_id):
    user = current_app.discord.fetch_user()
    db = SessionLocal()
    try:
        member = db.query(QueueMember).filter_by(queue_id=queue_id, discord_id=str(user.id)).first()
        if member:
            db.delete(member)
            db.commit()
            flash("Left queue.", "success")
        else:
             flash("You are not in this queue.", "error")
    finally:
        db.close()
        
    return redirect(url_for("queue.list_queues"))

@bp.route("/queue/kick/<int:queue_id>/<string:target_discord_id>")
@requires_login
def kick_member(queue_id, target_discord_id):
    user = current_app.discord.fetch_user()
    db = SessionLocal()
    try:
        queue = db.query(Queue).filter_by(id=queue_id).first()
        if not queue:
            flash("Queue not found.", "error")
            return redirect(url_for("queue.list_queues"))
        
        # Security Check: Only the host can kick
        if queue.created_by != str(user.id):
            flash("Only the host can kick members.", "error")
            return redirect(url_for("queue.list_queues"))

        # Cannot kick self
        if target_discord_id == str(user.id):
            flash("You cannot kick yourself.", "error")
            return redirect(url_for("queue.list_queues"))

        member = db.query(QueueMember).filter_by(queue_id=queue_id, discord_id=target_discord_id).first()
        if member:
            db.delete(member)
            db.commit()
            flash(f"Kicked {member.rsn} from the queue.", "success")
        else:
            flash("User not found in queue.", "error")
    finally:
        db.close()
        
    return redirect(url_for("queue.list_queues"))