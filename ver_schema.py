import sqlite3

conn = sqlite3.connect("db.sqlite3")
cur = conn.cursor()

# Lista de tabelas que interessam
tabelas = ["AppLSD_family", "core_family"]

for tabela in tabelas:
    print("\n" + "="*80)
    print(f"=== CREATE TABLE {tabela} ===")
    cur.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name=?;", (tabela,))
    result = cur.fetchone()
    if result:
        print(result[0])
    else:
        print(f"Tabela '{tabela}' não existe.")
        continue

    print(f"\n=== COLUNAS DE {tabela} ===")
    cur.execute(f"PRAGMA table_info('{tabela}');")
    print(f"{'cid':<5} {'Nome':<35} {'Tipo':<15} {'NotNull':<8} {'Default':<15} {'PK':<3}")
    print("-" * 85)
    for row in cur.fetchall():
        cid, name, tipo, notnull, default, pk = row
        print(f"{cid:<5} {name:<35} {tipo:<15} {notnull:<8} {str(default):<15} {pk:<3}")

    # Contagem de registros
    cur.execute(f"SELECT COUNT(*) FROM {tabela};")
    count = cur.fetchone()[0]
    print(f"\nTotal de registros: {count}")

conn.close()
