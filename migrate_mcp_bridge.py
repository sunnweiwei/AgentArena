#!/usr/bin/env python3
"""
Database migration script to replace SSH fields with bridge_url
"""
import sqlite3
import sys

db_path = sys.argv[1] if len(sys.argv) > 1 else 'chat_data.db'

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Remove SSH columns and add bridge_url
try:
    cursor.execute('ALTER TABLE mcp_servers ADD COLUMN bridge_url TEXT')
    print('Added bridge_url column')
except sqlite3.OperationalError as e:
    if 'duplicate column' in str(e).lower():
        print('bridge_url column already exists')
    else:
        raise

# Note: We don't remove SSH columns to preserve existing data
# They will just be ignored by the new code

conn.commit()
conn.close()
print('Migration completed successfully')

