import sqlite3

conn = sqlite3.connect("db.sqlite3")  # use exatamente o NAME do settings.py
cur = conn.cursor()

cur.execute("SELECT COUNT(*), COUNT(DISTINCT cpf) FROM AppLSD_family;")
total, distintos = cur.fetchone()
print("Total de linhas em AppLSD_family:", total)
print("Total de CPFs distintos:", distintos)

cur.execute("SELECT id, cpf, responsible_name FROM AppLSD_family LIMIT 10;")
print("\nPrimeiras linhas:")
for row in cur.fetchall():
    print(row)

conn.close()
