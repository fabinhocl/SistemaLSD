import sqlite3

conn = sqlite3.connect("db.sqlite3")  # ou o nome que estiver no settings.py
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
print(cur.fetchall())

conn.close()