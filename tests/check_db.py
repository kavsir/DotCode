import os
import sqlite3

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_path = os.path.join(root_dir, ".dotcode", "graph.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

print("=== TABLES ===")
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
for t in tables:
    print(t[0])

print("\n=== SCHEMA ===")
schema = conn.execute("SELECT sql FROM sqlite_master WHERE type='table'").fetchall()
for s in schema:
    print(s[0])

print("\n=== SYMBOLS (10) ===")
for row in conn.execute("SELECT * FROM symbols LIMIT 10"):
    print(dict(row))

print("\n=== EDGES (10) ===")
for row in conn.execute("SELECT * FROM edges LIMIT 10"):
    print(dict(row))

print("\n=== STATS ===")
print(f"Symbols: {conn.execute('SELECT COUNT(*) FROM symbols').fetchone()[0]}")
print(f"Edges: {conn.execute('SELECT COUNT(*) FROM edges').fetchone()[0]}")

conn.close()
