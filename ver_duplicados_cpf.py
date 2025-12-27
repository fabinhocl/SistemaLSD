import pandas as pd

df = pd.read_csv("familias.csv", sep=";", encoding="utf-8", dtype=str, low_memory=False)
df.columns = df.columns.str.strip()

# Só registros com CPF preenchido
df_cpf = df[df['CPF'].notna()].copy()
df_cpf['CPF'] = df_cpf['CPF'].str.strip()

# Duplicados de CPF dentro do CSV
dups_cpf = df_cpf[df_cpf.duplicated(subset=['CPF'], keep=False)].sort_values('CPF')

print("=== CPFs duplicados dentro do CSV ===")
print(dups_cpf[['CPF', 'RESPONSAVEL FAMILIAR']])
print(f"\nTotal de linhas com CPF duplicado: {len(dups_cpf)}")
