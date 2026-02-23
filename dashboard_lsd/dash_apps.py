import dash
import dash_bootstrap_components as dbc
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
    if not df.empty:
        df['salary_range_legenda'] = df['salary_range'].map(salary_map)
        df['idade'] = df['birth_date'].apply(calcula_idade)
    return df

def calcula_idade(nascimento):
    if pd.isnull(nascimento):
        return None
    return date.today().year - pd.to_datetime(nascimento).year

# Defina o objeto figure
def create_family_figure(df_family):
    if df_family.empty:
        return px.bar(title='Faixa Salarial (sem dados)')
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


app = DjangoDash("LSDDashboard")

@app.callback(
    Output("conteudo-aba", "children"),
    Input("tabs-dashboard", "value"),
    Input("interval-component", "n_intervals"),
)
def renderizar_conteudo_aba(tab, n):
    df_family = get_family_dataframe()

    if tab == "tab-familias":
        if df_family.empty:
            return html.Div("Sem dados de famílias")

        cadastradas = len(df_family)
        ativas = df_family[df_family["status"] == "ativo"].shape[0]
        inativas = df_family[df_family["status"] != "ativo"].shape[0]

        fig_status = px.pie(df_family, names="status", title="Status: Ativas/Inativas")
        fig_salario = create_family_figure(df_family)
        fig_educacao = px.bar(df_family, x="education", title="Escolaridade")

        return html.Div(
            [
                html.Div(
                    [
                        html.Div(f"Famílias cadastradas: {cadastradas}",
                                 className="kpi-card"),
                        html.Div(f"Famílias ativas: {ativas}",
                                 className="kpi-card"),
                        html.Div(f"Famílias inativas: {inativas}",
                                 className="kpi-card"),
                    ],
                    style={
                        "display": "flex",
                        "gap": "16px",
                        "flexWrap": "wrap",
                        "marginBottom": "24px",
                    },
                ),
                html.Div(
                    [
                        dcc.Graph(figure=fig_status,
                                  style={"flex": "1", "minWidth": "300px"}),
                        dcc.Graph(figure=fig_salario,
                                  style={"flex": "1", "minWidth": "300px"}),
                    ],
                    style={"display": "flex", "gap": "24px", "flexWrap": "wrap"},
                ),
                dcc.Graph(figure=fig_educacao),
            ]
        )

    elif tab == "tab-alunos":
        # aqui você monta os gráficos dos ALUNOS
        return html.Div("Gráficos de alunos (a implementar)")

    elif tab == "tab-adultos":
        return html.Div("Gráficos de adultos (a implementar)")

    elif tab == "tab-turmas":
        return html.Div("Gráficos de turmas (a implementar)")

    elif tab == "tab-atividades":
        return html.Div("Gráficos de atividades (a implementar)")

@app.callback(
    Output('status-familias', 'children'),
    Input('interval-component', 'n_intervals')
)
def atualizar_status_familias(n):
    # Sempre buscar o dataframe atualizado do banco/dados
    #df_family = pd.DataFrame(list(Family.objects.all().values(
    df_family = get_family_dataframe()
    cadastradas = len(df_family)
    ativas = df_family[df_family['status']=='ativo'].shape[0]
    inativas = df_family[df_family['status']!='ativo'].shape[0]

    return [
        html.H4(f"Famílias cadastradas: {cadastradas}"),
        html.H4(f"Famílias ativas: {ativas}"),
        html.H4(f"Famílias inativas: {inativas}")
    ]

app.layout = html.Div([
    html.H2("Dashboard Integra+Lar"),

        dcc.Tabs(
            id="tabs-dashboard",
            value="tab-familias",
            children=[
                dcc.Tab(label="Famílias", value="tab-familias"),
                dcc.Tab(label="Alunos", value="tab-alunos"),
                dcc.Tab(label="Adultos", value="tab-adultos"),
                dcc.Tab(label="Turmas", value="tab-turmas"),
                dcc.Tab(label="Atividades", value="tab-atividades"),
            ],
            # opcional: estilos
        ),

        dcc.Interval(
            id="interval-component",
            interval=30 * 1000,
            n_intervals=0
        ),

        html.Div(id="conteudo-aba")   # aqui entra o conteúdo dinâmico
    ],
    style={
        "padding": "40px",
        "maxWidth": "1200px",
        "minWidth": "500px",
        "margin": "0 auto",
    },
)

@app.callback(
    Output('grafico_status', 'figure'),
    Output('grafico_salario', 'figure'),
    Output('grafico_educacao', 'figure'),
    Input('interval-component', 'n_intervals')
)
def atualizar_graficos(n):
    df_family = get_family_dataframe()
    if df_family.empty:
        return px.pie(title='Sem dados'), px.bar(title='Sem dados'), px.bar(title='Sem dados')

    fig_status = px.pie(df_family, names='status', title='Status: Ativas/Inativas')
    fig_salario = create_family_figure(df_family)
    fig_educacao = px.bar(df_family, x='education', title='Escolaridade')
    return fig_status, fig_salario, fig_educacao

if __name__ == '__main__':
    app.run_server(debug=True)