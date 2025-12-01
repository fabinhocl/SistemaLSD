import dash
from django_plotly_dash import DjangoDash
from dash import dcc, html, dash, dash_table
from dash.dependencies import Input, Output
from datetime import date

import plotly.express as px
import pandas as pd

from AppLSD.models import Family


# Query Family table and convert to DataFrame
def get_family_dataframe():
    qs = Family.objects.all()
    df = pd.DataFrame(list(qs.values(
        'id', 'registration_number', 'responsible_name', 'sex', 'birth_date',
        'marital_status', 'education', 'income_types', 'salary_range',
        'num_residents', 'has_pcd', 'has_adult', 'has_elderly', 'has_child',
        'status'
    )))
    salary_map = {
        "1_sm": "1 Salário Mínimo",
        "2_sm": "2 Salários Mínimos",
        # ...adicione outros conforme necessário
    }
    df['salary_range_legenda'] = df['salary_range'].map(salary_map)
    return df

# Defina o objeto figure
def create_family_figure():
    df_family = get_family_dataframe()
    figure = px.bar(
        df_family,
        x='salary_range_legenda',
        color='salary_range_legenda',
        title='Faixa Salarial'
    )


# Atualize layout dos eixos
    figure.update_layout(
        xaxis_title="Faixa Salarial",
        yaxis_title="Quantidade de Famílias"
    )
    return figure

def get_family_data():
    # Troque este exemplo pela consulta do seu banco ou API
    # df_family = pd.read_sql_query("SEU SELECT ...", CONEXAO)
    df_family = pd.DataFrame([
        {"status": "ativo"},
        {"status": "ativo"},
        {"status": "inativo"},
        {"status": "ativo"}
    ])
    return df_family
df_family = get_family_dataframe()
figure = create_family_figure()

def calcula_idade(nascimento):
    if pd.isnull(nascimento):
        return None
    return date.today().year - pd.to_datetime(nascimento).year

df_family['idade'] = df_family['birth_date'].apply(calcula_idade)

app = DjangoDash("LSDDashboard")
app.layout = html.Div([
    html.H2("Dashboard de Famílias"),
    dcc.Interval(
        id='interval-component',
        interval=30*1000,  # a cada 30 segundos
        n_intervals=0
    ),
    
    html.Div([
        html.H4(f"Famílias Cadastradas: {len(df_family)}"),
        html.H4(f"Famílias Ativas: {df_family[df_family['status']=='ativo'].shape[0]}"),
    ], style={'display': 'flex', 'gap': '45px', 'marginBottom': '30px', 'justifyContent': 'center'}),
    dcc.Graph(
        id="grafico_status",
        figure=px.pie(df_family, names='status', title='Status: Ativas/Inativas'),
        style={'height': '420px', 'width': '88vw', 'maxWidth': '900px'}
    ),
    dcc.Graph(
        id="grafico_salario",
        figure=figure,
        style={'height': '420px', 'width': '88vw', 'maxWidth': '900px'}
    ),
     
    
    dcc.Graph(
        id="grafico_educacao",
        figure=px.bar(df_family, x='education', title='Escolaridade'),
        style={'height': '420px', 'width': '88vw', 'maxWidth': '900px'}
    ),
        
], style={'display':'flex','flexDirection':'column','alignItems':'center','gap':'24px', 'padding':'50px', 'paddingTop': '12px'})

@app.callback(
    Output('status-familias', 'children'),
    Input('interval-component', 'n_intervals')
)
def atualizar_status_familias(n):
    # Sempre buscar o dataframe atualizado do banco/dados
    #df_family = pd.DataFrame(list(Family.objects.all().values(
    cadastradas = len(df_family)
    ativas = df_family[df_family['status']=='ativo'].shape[0]
    inativas = df_family[df_family['status']!='ativo'].shape[0]

    return [
        html.H4(f"Famílias cadastradas: {cadastradas}"),
        html.H4(f"Famílias ativas: {ativas}"),
        html.H4(f"Famílias inativas: {inativas}")
    ]
if __name__ == '__main__':
    app.run_server(debug=True)