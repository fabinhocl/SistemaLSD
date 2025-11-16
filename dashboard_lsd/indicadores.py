def count_ativos(df, status_col='status'):
    return df[df[status_col] == 'Ativo'].shape[0]

def count_inativos(df, status_col='status'):
    return df[df[status_col] == 'Inativo'].shape[0]

def group_by_sexo(df, sexo_col='sexo'):
    return df.groupby(sexo_col).size().to_dict()

def group_by_faixa_etaria(df, idade_col='idade'):
    def faixa(idade):
        if idade < 6: return '0-5'
        elif idade < 12: return '6-11'
        elif idade < 18: return '12-17'
        elif idade < 30: return '18-29'
        elif idade < 60: return '30-59'
        else: return '60+'
    df['faixa_etaria'] = df[idade_col].apply(faixa)
    return df.groupby('faixa_etaria').size().to_dict()
