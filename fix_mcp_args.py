#!/usr/bin/env python3
import sqlite3
import json
import sys

db_path = sys.argv[1] if len(sys.argv) > 1 else 'chat_data.db'
server_id = sys.argv[2] if len(sys.argv) > 2 else 'mcp_5_1766190911'

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Fix the args - use a path that exists on the server for testing
# Change this back to local path after we verify MCP works
args = ['-y', '@modelcontextprotocol/server-filesystem', '/usr1/data/weiweis/chat_server']
args_json = json.dumps(args)

cursor.execute('UPDATE mcp_servers SET args = ? WHERE server_id = ?', (args_json, server_id))
conn.commit()

# Verify
cursor.execute('SELECT server_id, args FROM mcp_servers WHERE server_id = ?', (server_id,))
result = cursor.fetchone()
if result:
    print(f'Updated: server_id={result[0]}')
    print(f'Args: {result[1]}')
    # Verify it's valid JSON
    try:
        parsed = json.loads(result[1])
        print(f'Parsed args: {parsed}')
    except:
        print('ERROR: Args are not valid JSON!')
else:
    print(f'Server {server_id} not found')

conn.close()

