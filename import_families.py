import os
import django
import pandas as pd
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'larsaodomingos.settings')
django.setup()

from AppLSD.models import Family

# Lê o arquivo CSV (ajuste 'sep' se necessário)
df = pd.read_csv('familias.csv', encoding='utf-8', sep=';')

for index, row in df.iterrows():
    try:
        # Função de conversão segura para inteiro
        def safe_int(value, default=0):
            if pd.isna(value) or str(value).strip() == '':
                return default
            else:
                try:
                    return int(float(value))
                except Exception:
                    return default

        # Função de conversão segura para booleano
        def safe_bool(value):
            return str(value).strip().upper() == 'SIM'

        # Função de conversão segura para string
        def safe_str(value):
            if pd.isna(value):
                return ''
            return str(value).strip()

        # Função segura para data
        def safe_date(value):
            if pd.isna(value) or str(value).strip() == "":
                return None
            try:
                return datetime.strptime(str(value), '%d/%m/%Y').date()
            except Exception:
                return None

        fam = Family(
            registration_number=safe_str(row.get('NUMERO INSCRIÇÃO')),
            responsible_name=safe_str(row.get('RESPONSAVEL FAMILIAR')),
            nis=safe_str(row.get('NIS DO RESPONSAVEL')),
            rg=safe_str(row.get('RG')),
            cpf=safe_str(row.get('CPF')),
            birth_date=safe_date(row.get('DATA NASCIMENTO')),
            sex=safe_str(row.get('SEXO')),
            address=safe_str(row.get('ENDEREÇO')),
            neighborhood=safe_str(row.get('BAIRRO')),
            reference_point=safe_str(row.get('PONTO DE REFERENCIA')),
            telephone=safe_str(row.get('TELEFONE')),
            marital_status=safe_str(row.get('ESTADO CIVIL')),
            education=safe_str(row.get('ESCOLARIDADE')),
            race=safe_str(row.get('RAÇA (AUTODECLARADO)')),
            religion=safe_str(row.get('ASPECTO RELIGIOSO DA FAMÍLIA')),
            social_benefits=safe_str(row.get('BENEFICIARIA DE PROGRAMAS SOCIAIS')),
            occupation=safe_str(row.get('OCUPAÇÃO PROFISSÃO')),
            has_proven_income=safe_bool(row.get('POSSUI RENDA COMPROVADA')),
            min_salary_1=safe_bool(row.get('1 SALARIO MINIMO')),
            min_salary_2=safe_bool(row.get('2 SALARIOS MINIMOS')),
            others_contribute=safe_bool(row.get('OUTRAS PESSOAS CONTRIBUEM COM A RENDA DA FAMILIA')),
            who_contributes=safe_str(row.get('QUEM')),
            num_residents=safe_int(row.get('QUANTAS PESSOAS RESIDEM NO DOMICILIO')),
            has_elderly=safe_bool(row.get('IDOSO')),
            has_adolescent=safe_bool(row.get('ADOLESCENTE')),
            has_child=safe_bool(row.get('CRIANÇA')),
            has_pregnant=safe_bool(row.get('GESTANTE')),
            file_info=safe_str(row.get('Arquivo'))
        )
        fam.save()
    except Exception as e:
        print(f'Erro ao importar registro {index}: {e}')

print("Importação concluída.")
