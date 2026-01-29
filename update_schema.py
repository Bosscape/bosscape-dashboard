from db import engine
from sqlalchemy import text

def migrate():
    print("Migrating database...")
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE queues ADD COLUMN description TEXT;"))
            conn.commit()
            print("Successfully added 'description' column to 'queues' table.")
        except Exception as e:
            print(f"Migration failed (Column might already exist): {e}")

if __name__ == "__main__":
    migrate()
