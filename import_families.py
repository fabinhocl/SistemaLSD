import pandas as pd
import sqlite3
from sqlalchemy import create_engine
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# 1. Ler CSV
df = pd.read_csv(BASE_DIR / "familias_apenas_validas.csv",
                 sep=";", encoding="utf-8", dtype=str, low_memory=False)
df.columns = df.columns.str.strip()

# 2. Manter só linhas com número de inscrição
df = df[df['NUMERO INSCRIÇÃO'].notna()]
df = df[df['NUMERO INSCRIÇÃO'].astype(str).str.strip() != ""]

print(f"Total de cadastros válidos no CSV: {len(df)}")


def sim_nao_to_int(val):
    if pd.isna(val):
        return 0
    val = str(val).strip().lower()
    return 1 if val in ['sim', 's', 'yes', '1', 'true'] else 0


def converter_data(val):
    if pd.isna(val) or str(val).strip() == '':
        return None
    try:
        return datetime.strptime(str(val).strip(), '%d/%m/%Y').strftime('%Y-%m-%d')
    except:
        return None


# 3. Montar df_insert
df_insert = pd.DataFrame()
df_insert['registration_number'] = df['NUMERO INSCRIÇÃO'].astype(str).str.strip()
df_insert['responsible_name'] = df['RESPONSAVEL FAMILIAR'].fillna('').str.strip()
df_insert['nis'] = df['NIS DO RESPONSAVEL'].fillna('')
df_insert['rg'] = df['RG'].fillna('')
df_insert['cpf'] = df['CPF'].fillna('')
df_insert['birth_date'] = df['DATA NASCIMENTO'].apply(converter_data)
df_insert['sex'] = df['SEXO'].fillna('')
df_insert['address'] = df['ENDEREÇO'].fillna('')
df_insert['neighborhood'] = df['BAIRRO'].fillna('Não informado')
df_insert['reference_point'] = df['PONTO DE REFERENCIA'].fillna('')
df_insert['telephone'] = df['TELEFONE'].fillna('')
df_insert['marital_status'] = df['ESTADO CIVIL'].fillna('')
df_insert['education'] = df['ESCOLARIDADE'].fillna('')
df_insert['race'] = df['RAÇA (AUTODECLARADO)'].fillna('')
df_insert['religion'] = df['ASPECTO RELIGIOSO DA FAMÍLIA'].fillna('')
df_insert['social_benefits'] = df['BENEFICIARIA DE PROGRAMAS SOCIAIS'].fillna('')
df_insert['occupation'] = df['OCUPAÇÃO PROFISSÃO'].fillna('')
df_insert['has_proven_income'] = df['POSSUI RENDA COMPROVADA'].apply(
    lambda x: 'Sim' if sim_nao_to_int(x) else 'Não'
)
df_insert['num_residents'] = df['QUANTAS PESSOAS RESIDEM NO DOMICILIO'].fillna(1).astype(int)
df_insert['has_elderly'] = df['IDOSO'].apply(sim_nao_to_int)
df_insert['has_adolescent'] = df['ADOLESCENTE'].apply(sim_nao_to_int)
df_insert['has_child'] = df['CRIANÇA'].apply(sim_nao_to_int)
df_insert['has_pregnant'] = df['GESTANTE'].apply(sim_nao_to_int)
df_insert['file_info'] = df['Arquivo'].fillna('')

# 4. Campos padrão obrigatórios
agora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
df_insert['is_working'] = 'Não'
df_insert['others_contribute'] = 'Não'
df_insert['function'] = 'Responsável'
df_insert['is_benefits'] = 'Não'
df_insert['social_name'] = df_insert['responsible_name']
df_insert['has_pcd'] = 0
df_insert['has_adult'] = 0
df_insert['mae_solo'] = 'Não'
df_insert['income_types'] = '[]'
df_insert['criado_em'] = agora
df_insert['editado_em'] = agora
df_insert['excluido'] = 0

print("\nPrimeiras 3 linhas preparadas:")
print(df_insert.head(3))

# 5. CPF: normalizar e remover duplicados
# Normaliza CPF; vazio vira None para não violar UNIQUE
df_insert['cpf'] = df_insert['cpf'].fillna('').astype(str).str.strip()
df_insert['cpf'] = df_insert['cpf'].replace('', None)

mask_nao_vazio = df_insert['cpf'] != ''

dups = df_insert[mask_nao_vazio & df_insert.duplicated(subset=['cpf'], keep=False)].copy()
dups = dups.sort_values('cpf')
print("\n=== CPFs duplicados dentro do df_insert (antes de remover) ===")
print(dups[['cpf', 'responsible_name']])
print("Total de linhas duplicadas no df_insert:", len(dups))

duplicados_mask = df_insert.duplicated(subset=['cpf'], keep='first') & mask_nao_vazio
df_ignorados = df_insert[duplicados_mask].copy()
df_insert = df_insert[~duplicados_mask].copy()

print("\nRegistros ignorados por CPF duplicado no df_insert:", len(df_ignorados))
if not df_ignorados.empty:
    relatorio_path = BASE_DIR / "familias_duplicadas_no_df_insert.csv"
    df_ignorados.to_csv(relatorio_path, sep=";", index=False, encoding="utf-8")
    print(f"Relatório de duplicados no df_insert salvo em: {relatorio_path}")

print(f"\nTotal de registros a importar depois de remover duplicados: {len(df_insert)}")

# 6. Inserir no SQLite
engine = create_engine(
        "postgresql+psycopg2://lsd_user:Sys.Admin!@#098@localhost:5432/lsd"
    )

df_insert.to_sql('AppLSD_family', engine, if_exists='append', index=False)
    
print(f"\n✓ {len(df_insert)} cadastros importados com sucesso para AppLSD_family!")
except Exception as e:
    print(f"\n✗ Erro ao importar: {e}")
    print("\nVerifique se há duplicatas em registration_number ou cpf.")

conn.close()
