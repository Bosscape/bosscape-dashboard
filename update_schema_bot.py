from db import engine
from sqlalchemy import text

def migrate():
    print("Migrating database for Bot...")
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE queues ADD COLUMN discord_message_id TEXT;"))
            conn.execute(text("ALTER TABLE queues ADD COLUMN discord_channel_id TEXT;"))
            conn.commit()
            print("Successfully added Discord columns to 'queues' table.")
        except Exception as e:
            print(f"Migration might have partially failed (Columns might exist): {e}")

if __name__ == "__main__":
    migrate()
