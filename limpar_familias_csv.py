import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

csv_path = BASE_DIR / "familias_sem_duplicados.csv"   # ou diretamente "familias.csv"
df = pd.read_csv(csv_path, sep=";", encoding="utf-8", dtype=str, low_memory=False)

df.columns = df.columns.str.strip()

# mantém só linhas onde NUMERO INSCRIÇÃO não é vazio e não é NaN
mask_validas = df['NUMERO INSCRIÇÃO'].notna() & (df['NUMERO INSCRIÇÃO'].astype(str).str.strip() != "")

df_validas = df[mask_validas].copy()

print(f"Total de linhas originais: {len(df)}")
print(f"Total de cadastros válidos: {len(df_validas)}")

saida_path = BASE_DIR / "familias_apenas_validas.csv"
df_validas.to_csv(saida_path, sep=";", index=False, encoding="utf-8")
print(f"CSV só com cadastros válidos salvo em: {saida_path}")
