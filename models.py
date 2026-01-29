# models.py

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

# --- User & Stats ---
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    discord_id = Column(String, unique=True, nullable=False)
    rsn = Column(String, nullable=False)
    linked_at = Column(DateTime, default=datetime.utcnow)

    snapshots = relationship("StatSnapshot", back_populates="user")

class StatSnapshot(Base):
    __tablename__ = "snapshots"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    stats = Column(JSON, nullable=False)

    user = relationship("User", back_populates="snapshots")

# --- Queue System ---
class Queue(Base):
    __tablename__ = "queues"

    id = Column(Integer, primary_key=True)
    boss = Column(String, nullable=False)  # Boss/Raid/Event name
    role = Column(String, nullable=False)  # learner/teacher/etc.
    group_size = Column(Integer, nullable=False)  # 2–100
    expires_at = Column(DateTime, nullable=False)
    created_by = Column(String, nullable=False)  # Discord ID
    created_at = Column(DateTime, default=datetime.utcnow)
    description = Column(String, nullable=True)  # Notes
    discord_message_id = Column(String, nullable=True)
    discord_channel_id = Column(String, nullable=True)

    members = relationship("QueueMember", back_populates="queue", cascade="all, delete")

class QueueMember(Base):
    __tablename__ = "queue_members"

    id = Column(Integer, primary_key=True)
    queue_id = Column(Integer, ForeignKey("queues.id"), nullable=False)
    discord_id = Column(String, nullable=False)
    rsn = Column(String, nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)

    queue = relationship("Queue", back_populates="members")

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    discord_id = Column(String, nullable=False)
    message = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)