#!/usr/bin/env python3
"""
Database migration script to add new columns for labeling features.
Run this script to update the database schema without losing data.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.core.database import engine, SessionLocal

def run_migration():
    """Add new columns to existing tables"""
    
    migrations = [
        # Add dataset_id to segments
        ("segments", "dataset_id", "ALTER TABLE segments ADD COLUMN IF NOT EXISTS dataset_id INTEGER REFERENCES datasets(id)"),
        
        # Add review_comment to segments
        ("segments", "review_comment", "ALTER TABLE segments ADD COLUMN IF NOT EXISTS review_comment TEXT"),
        
        # Add version to annotations
        ("annotations", "version", "ALTER TABLE annotations ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1"),
        
        # Add role to users (if not exists)
        ("users", "role", "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(50) DEFAULT 'annotator'"),
    ]
    
    # Create datasets table if not exists
    create_datasets = """
    CREATE TABLE IF NOT EXISTS datasets (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL UNIQUE,
        description TEXT,
        created_by INTEGER REFERENCES users(id),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE
    )
    """
    
    db = SessionLocal()
    
    try:
        # Create datasets table first
        print("Creating datasets table if not exists...")
        db.execute(text(create_datasets))
        db.commit()
        print("✓ Datasets table ready")
        
        # Run column migrations
        for table, column, sql in migrations:
            try:
                print(f"Adding {column} to {table}...")
                db.execute(text(sql))
                db.commit()
                print(f"✓ Added {column} to {table}")
            except Exception as e:
                db.rollback()
                if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                    print(f"✓ Column {column} already exists in {table}")
                else:
                    print(f"⚠ Warning for {table}.{column}: {e}")
        
        print("\n✅ Database migration completed successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 50)
    print("ViSL Tool - Database Migration")
    print("=" * 50)
    run_migration()

