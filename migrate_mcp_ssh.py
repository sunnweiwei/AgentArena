#!/usr/bin/env python3
"""
Database migration script to add SSH fields to mcp_servers table
"""
import sqlite3
import sys

db_path = sys.argv[1] if len(sys.argv) > 1 else 'chat_data.db'

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Add SSH columns if they don't exist
try:
    cursor.execute('ALTER TABLE mcp_servers ADD COLUMN ssh_host TEXT')
    print('Added ssh_host column')
except sqlite3.OperationalError as e:
    if 'duplicate column' in str(e).lower():
        print('ssh_host column already exists')
    else:
        raise

try:
    cursor.execute('ALTER TABLE mcp_servers ADD COLUMN ssh_user TEXT')
    print('Added ssh_user column')
except sqlite3.OperationalError as e:
    if 'duplicate column' in str(e).lower():
        print('ssh_user column already exists')
    else:
        raise

try:
    cursor.execute('ALTER TABLE mcp_servers ADD COLUMN ssh_port INTEGER DEFAULT 22')
    print('Added ssh_port column')
except sqlite3.OperationalError as e:
    if 'duplicate column' in str(e).lower():
        print('ssh_port column already exists')
    else:
        raise

try:
    cursor.execute('ALTER TABLE mcp_servers ADD COLUMN ssh_key TEXT')
    print('Added ssh_key column')
except sqlite3.OperationalError as e:
    if 'duplicate column' in str(e).lower():
        print('ssh_key column already exists')
    else:
        raise

conn.commit()
conn.close()
print('Migration completed successfully')

