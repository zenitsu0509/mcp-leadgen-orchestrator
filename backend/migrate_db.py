"""
Database migration script to add phone, comments, and source fields to leads table.
Run this once to update your existing database.
"""
import sqlite3
import os

DB_PATH = "./data/leads.db"

def migrate_database():
    """Add new columns to existing leads table"""
    if not os.path.exists(DB_PATH):
        print("❌ Database not found. Run 'python backend/database.py' first.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(leads)")
        columns = [col[1] for col in cursor.fetchall()]
        
        migrations_needed = []
        
        if 'phone' not in columns:
            migrations_needed.append("ALTER TABLE leads ADD COLUMN phone TEXT")
        
        if 'comments' not in columns:
            migrations_needed.append("ALTER TABLE leads ADD COLUMN comments TEXT")
        
        if 'source' not in columns:
            migrations_needed.append("ALTER TABLE leads ADD COLUMN source TEXT")
        
        if not migrations_needed:
            print("✅ Database already up to date!")
            return
        
        # Apply migrations
        for migration in migrations_needed:
            print(f"Running: {migration}")
            cursor.execute(migration)
        
        conn.commit()
        print(f"\n✅ Successfully added {len(migrations_needed)} new column(s) to leads table!")
        print("   - phone: TEXT")
        print("   - comments: TEXT") 
        print("   - source: TEXT")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("🔧 Starting database migration...\n")
    migrate_database()
    print("\n✨ Migration complete!")
