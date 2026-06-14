# -*- coding: utf-8 -*-
import dash
import dash_bootstrap_components as dbc
from django_plotly_dash import DjangoDash
from dash import dcc, html, dash, dash_table
from dash.dependencies import Input, Output
from datetime import date

import plotly.express as px
import pandas as pd

from AppLSD.models import Family, Aluno, Adult, Turma, Activity


# ----------------- Helpers -----------------

def calcula_idade(nascimento):
    if pd.isnull(nascimento):
        return None
    hoje = date.today()
    nasc = pd.to_datetime(nascimento)
    return hoje.year - nasc.year - ((hoje.month, hoje.day) < (nasc.month, nasc.day))


def criar_fig_bar(df, x, y, titulo, x_title, y_title, orientation='v'):
    fig = px.bar(
        df,
        x=x if orientation == 'v' else y,
        y=y if orientation == 'v' else x,
        text=y if orientation == 'v' else x,
        orientation=orientation,
        title=titulo,
    )
    fig.update_traces(textposition='outside', cliponaxis=False)
    fig.update_layout(
        title={"text": f"<b>{titulo}</b>", "x": 0.5, "xanchor": "center"},
        xaxis_title=x_title,
        yaxis_title=y_title,
    )
    return fig


# ---------- DATAFRAMES ----------

def get_family_dataframe():
    qs = Family.objects.all().values(
        'id', 'registration_number', 'responsible_name', 'birth_date', 'sex',
        'mae_solo', 'gestante', 'neighborhood', 'marital_status', 'education',
        'race', 'religion', 'social_benefits', 'occupation', 'has_proven_income',
        'salary_range', 'domicile_type', 'status',
    )
    df = pd.DataFrame(list(qs))
    if df.empty:
        return df

    df['idade'] = df['birth_date'].apply(calcula_idade)
    df['faixa_etaria'] = pd.cut(
        df['idade'],
        bins=[18, 29, 39, 49, 59, 100],
        labels=['18-29', '30-39', '40-49', '50-59', '60+'],
        right=True,
    )

    salary_map = {
        '1_sm': '1 Salário Mínimo',
        '2_sm': '2 Salários Mínimos',
        '3_sm': '3 Salários Mínimos+',
    }
    df['salary_range_legenda'] = df['salary_range'].map(salary_map).fillna(df['salary_range'])
    return df


def get_alunos_dataframe():
    qs = Aluno.objects.all().values(
        'id', 'sex', 'birth_date', 'school', 'rede_ensino', 'serie', 'ensino', 'turno',
        'health_problem', 'special_need', 'uso_medicacao', 'qual_medicacao',
        'frequencia_tipo', 'dias_semana', 'status_lsd',
    )
    df = pd.DataFrame.from_records(qs)
    if df.empty:
        return df

    df['birth_date'] = pd.to_datetime(df['birth_date'])
    df['idade'] = df['birth_date'].apply(calcula_idade)

    df['publico_dashboard'] = pd.cut(
        df['idade'],
        bins=[5, 12, 17],
        labels=['Crianças (6 a 12 anos)', 'Adolescentes (13 a 17 anos)'],
        right=True,
        include_lowest=True,
    )

    df['faixa_etaria_alunos'] = pd.cut(
        df['idade'],
        bins=[6, 7, 9, 12, 17],
        labels=['6-7', '8-9', '10-12', '13-17'],
        right=True,
        include_lowest=True,
    )
    return df


def get_adult_dataframe():
    qs = Adult.objects.all().values(
        'id', 'sex', 'birth_date', 'status_lsd'
    )
    df = pd.DataFrame(list(qs))
    if df.empty:
        return df

    df['birth_date'] = pd.to_datetime(df['birth_date'])
    df['idade'] = df['birth_date'].apply(calcula_idade)
    df['faixa_etaria_idosos'] = pd.cut(
        df['idade'],
        bins=[59, 69, 79, 89, 120],
        labels=['60-69', '70-79', '80-89', '90+'],
        right=True,
        include_lowest=True,
    )
    return df


def get_turmas_dataframe():
    qs = Turma.objects.all().values(
        'id', 'name', 'educatora__name', 'turno', 'status'
    )
    return pd.DataFrame(list(qs))


def get_activities_dataframe():
    qs = Activity.objects.all().values(
        'id', 'name', 'status'
    )
    return pd.DataFrame(list(qs))


# ---------- APP ----------

app = DjangoDash(
    'LSDDashboard',
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
)

app.layout = html.Div(
    [
        dbc.Tabs(
            id='tabs-dashboard',
            active_tab='tab-familias',
            children=[
                dbc.Tab(label='Famílias', tab_id='tab-familias'),
                dbc.Tab(label='Alunos', tab_id='tab-alunos'),
                dbc.Tab(label='Idosos', tab_id='tab-idosos'),
                dbc.Tab(label='Turmas', tab_id='tab-turmas'),
                dbc.Tab(label='Atividades', tab_id='tab-atividades'),
            ],
            className='mb-3',
        ),
        dcc.Interval(id='interval-component', interval=30 * 1000, n_intervals=0),
        html.Div(id='conteudo-aba'),
    ],
    className='container-fluid py-3',
)


# ---------- CALLBACK PRINCIPAL ----------

@app.callback(
    Output('conteudo-aba', 'children'),
    Input('tabs-dashboard', 'active_tab'),
    Input('interval-component', 'n_intervals'),
)
def renderizar_conteudo_aba(tab, n):
    if tab == "tab-familias":
        df_family = get_family_dataframe()
        if df_family.empty:
            return html.Div("Sem dados de famílias cadastradas.")

        df_ativas = df_family[df_family["status"] == "ativo"].copy()
        
        
        cadastradas = len(df_family)
        ativas = len(df_ativas)
        #inativas = cadastradas - ativas
        gestantes = df_ativas[df_ativas["gestante"] == "Sim"].shape[0]
        nutriz = df_ativas[df_ativas["gestante"] == "Nutriz"].shape[0]

        # --------- GRÁFICOS ---------
       
        # Faixa salarial
        fig_salario = px.bar(
            df_ativas,
            x="salary_range_legenda",
            title="Faixa salarial das famílias",
            text_auto=True,
        )
        fig_salario.update_traces(
            textposition="outside",
            textfont_size=12,
            cliponaxis=False,
        )
        fig_salario.update_layout(
            title={"text": "<b>Faixa salarial das famílias</b>", "x": 0.5, "xanchor": "center"},
            xaxis_title="Faixa salarial",
            yaxis_title="Quantidade de famílias",
        )

       # -------- estado civil --------
        estado_counts = (
            df_ativas["marital_status"]
            .value_counts()
            .reset_index()
        )
        estado_counts.columns = ["marital_status", "qtd"]

        fig_estado_civil = px.bar(
            estado_counts,
            x="marital_status",
            y="qtd",
            title="Famílias por estado civil",
            text="qtd",
        )
        fig_estado_civil.update_traces(textposition="outside", cliponaxis=False)
        fig_estado_civil.update_layout(
            title={"text": "<b>Famílias por estado civil</b>", "x": 0.5, "xanchor": "center"},
            xaxis_title="Estado civil",
            yaxis_title="Quantidade de famílias",
        )

        # -------- escolaridade --------
        edu_counts = (
            df_ativas["education"]
            .value_counts()
            .reset_index()
        )
        edu_counts.columns = ["education", "qtd"]

        fig_educacao = px.bar(
            edu_counts,
            x="education",
            y="qtd",
            title="Escolaridade do responsável",
            text="qtd",
        )
        fig_educacao.update_traces(textposition="outside", cliponaxis=False)
        fig_educacao.update_layout(
            title={"text": "<b>Escolaridade do responsável</b>", "x": 0.5, "xanchor": "center"},
            xaxis_title="Escolaridade",
            yaxis_title="Quantidade de famílias",
        )

        # -------- sexo --------
        sexo_counts = (
            df_ativas["sex"]
            .value_counts()
            .reset_index()
        )
        sexo_counts.columns = ["sex", "qtd"]

        fig_sexo = px.bar(
            sexo_counts,
            x="sex",
            y="qtd",
            title="Famílias por sexo do responsável",
            
            text="qtd",
        )
        fig_sexo.update_traces(textposition="outside", cliponaxis=False)
        fig_sexo.update_layout(
            title={"text": "<b>Famílias por sexo do responsável</b>", "x": 0.5, "xanchor": "center"},
            xaxis_title="Sexo",
            yaxis_title="Quantidade de famílias",
        )
       # -------- faixas etárias --------
        faixa_counts = (
            df_ativas["faixa_etaria"]
            .value_counts()
            .sort_index()
            .reset_index()
        )
        faixa_counts.columns = ["faixa_etaria", "qtd"]

        fig_faixa = px.bar(
            faixa_counts,
            x="faixa_etaria",
            y="qtd",
            title="Famílias por faixa etária do responsável", 
            text="qtd",
        )
        fig_faixa.update_traces(textposition="outside", cliponaxis=False)
        fig_faixa.update_layout(
            title={"text": "<b>Famílias por faixa etária do responsável</b>", "x": 0.5, "xanchor": "center"},
            xaxis_title="Faixa etária",
            yaxis_title="Quantidade de famílias",
        )


       # -------- Mãe Solo --------
        mae_solo_counts = (
            df_ativas["mae_solo"]
            .value_counts()
            .reset_index()
        )
        mae_solo_counts.columns = ["mae_solo", "qtd"]

        fig_mae_solo = px.bar(
            mae_solo_counts,
            x="mae_solo",
            y="qtd",
            title="Mães Solo",
            text="qtd",
        )
        fig_mae_solo.update_traces(textposition="outside", cliponaxis=False)
        fig_mae_solo.update_layout(
            title={"text": "<b>Mães Solo</b>", "x": 0.5, "xanchor": "center"},
            xaxis_title="Mãe Solo",
            yaxis_title="Quantidade de Mãe solo",
        )

        # -------- Bairro --------
        bairros_counts = (
            df_ativas["neighborhood"]
            .value_counts()
            .reset_index()
        )
        bairros_counts.columns = ["neighborhood", "qtd"]

        fig_bairros = px.bar(
            bairros_counts,
            x="neighborhood",
            y="qtd",
            title="Bairro",
            text="qtd",
        )
        fig_bairros.update_traces(textposition="outside", cliponaxis=False)
        fig_bairros.update_layout(
            title={"text": "<b>Bairro</b>", "x": 0.5, "xanchor": "center"},
            xaxis_title="Bairro",
            yaxis_title="Família por Bairro",
        )

       # -------- Benefícios sociais --------
       # df_ativas já filtrado só com status='ativo'

        # df_ativas: dataframe só com famílias ativas
        # social_benefits vem como lista (array do Postgres)
        def normalizar_beneficios(valor):
            if not valor:
                return "Sem benefício"
            # se vier lista, pega cada item não vazio
            if isinstance(valor, (list, tuple)):
                if len(valor) == 0:
                    return "Sem benefício"
                # se aceitar múltiplos benefícios por família, junte por vírgula
                return ", ".join([v for v in valor if v])
            # fallback: string simples
            return valor or "Sem benefício"

        df_ativas["beneficio_str"] = df_ativas["social_benefits"].apply(normalizar_beneficios)

        beneficios_counts = (
            df_ativas["beneficio_str"]
            .value_counts()
            .reset_index()
        )
        beneficios_counts.columns = ["beneficio", "qtd"]

        fig_beneficios = px.bar(
            beneficios_counts,
            x="beneficio",
            y="qtd",
            title="Famílias por benefício social",
            text="qtd",
        )
        fig_beneficios.update_traces(textposition="outside", cliponaxis=False)
        fig_beneficios.update_layout(
            title={"text": "<b>Famílias por benefício social</b>", "x": 0.5, "xanchor": "center"},
            xaxis_title="Benefícios sociais",
            yaxis_title="Quantidade de famílias",
        )

        # -------- Religião --------
        religiao_counts = (
            df_ativas["religion"]
            .value_counts()
            .reset_index()
        )
        religiao_counts.columns = ["religion", "qtd"]

        fig_religiao = px.bar(
            religiao_counts,
            y="religion",
            x="qtd",
            title="Religião",
            text="qtd",
            orientation="h",
        )
        fig_religiao.update_traces(textposition="outside", cliponaxis=False)
        fig_religiao.update_layout(
            title={"text": "<b>Religião</b>", "x": 0.5, "xanchor": "center"},
            xaxis_title="Religião",
            yaxis_title="Quantidade de famílias",
        )

        # -------- Ocupação --------
        ocupacao_counts = (
            df_ativas["occupation"]
            .fillna("Não informado")
            .str.strip()
            .value_counts()
            .reset_index()
        )
        ocupacao_counts.columns = ["occupation", "qtd"]

        # top 10 em ordem decrescente
        top10_ocup = ocupacao_counts.head(10)
        fig_ocupacao = px.bar(
            top10_ocup,
            x="occupation",
            y="qtd",
            title="Principais ocupações dos responsáveis",
            text="qtd",
            orientation="v",
        )
        fig_ocupacao.update_traces(textposition="outside", cliponaxis=False)
        fig_ocupacao.update_layout(
            title={"text": "<b>Principais ocupações dos responsáveis</b>", "x": 0.5, "xanchor": "center",},
            yaxis_title="Quantidade de famílias",
            xaxis_title="Ocupação",
            width=700,   # por exemplo
            height=400,
            margin=dict(l=80, r=40, t=60, b=80),
        )

        # --------- LAYOUT (CARDS + GRÁFICOS) ---------
        kpi_cards = dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                        [
                            html.H6("Famílias cadastradas", className="text-muted mb-2 text-center"),
                            html.H3(f"{cadastradas}", className="mb-0 text-center"),
                            ]
                        ),
                        className="mb-3 shadow-sm",
                    ),
                    md=3,
                ),
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                html.H6("Famílias ativas", className="text-muted mb-2 text-center"),
                                html.H3(f"{ativas}", className="mb-0 text-success text-center"),
                            ]
                        ),
                        className="shadow-sm",
                    ),
                    md=3,
                ),
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                html.H6("Gestantes", className="text-muted mb-2 text-center"),
                                html.H3(f"{gestantes}", className="mb-0 text-danger text-center"),
                            ]
                        ),
                        className="shadow-sm",
                    ),
                    md=3,
                ),
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                html.H6("Nutriz", className="text-muted mb-2 text-center"),
                                html.H3(f"{nutriz}", className="mb-0 text-primary text-center"),
                            ]
                        ),
                        className="shadow-sm",
                    ),
                    md=3,
                ),
            ],
            className="mb-4 g-3",  # g-3 dá espaçamento entre colunas
        )
        

        return html.Div(
            [
                kpi_cards,

                # Linha 1
                html.Div(
                    [
                        dcc.Graph(figure=fig_educacao, style={"flex": "1", "minWidth": "300px"}),
                        dcc.Graph(figure=fig_sexo, style={"flex": "1", "minWidth": "300px"}),
                        
                    ],
                    style={"display": "flex", "gap": "24px", "flexWrap": "wrap"},
                ),

                # Linha 2
                html.Div(
                    [
                        dcc.Graph(figure=fig_faixa, style={"flex": "1", "minWidth": "300px"}),
                        dcc.Graph(figure=fig_estado_civil, style={"flex": "1", "minWidth": "300px"}),
                        
                    ],
                    style={"display": "flex", "gap": "24px", "flexWrap": "wrap"},
                ),

                # Linha 3
                html.Div(
                    [
                        dcc.Graph(figure=fig_mae_solo, style={"flex": "1", "minWidth": "300px"}),
                        dcc.Graph(figure=fig_bairros, style={"flex": "1", "minWidth": "300px"}),
                    ],
                    style={"display": "flex", "gap": "24px", "flexWrap": "wrap"},
                ),

                # Linha 4
                html.Div(
                    [
                        dcc.Graph(figure=fig_beneficios, style={"flex": "1", "minWidth": "300px"}),
                        dcc.Graph(figure=fig_religiao, style={"flex": "1", "minWidth": "300px"}),
                    ],
                    style={"display": "flex", "gap": "24px", "flexWrap": "wrap"},
                ),

                # Linha 5
                html.Div(
                    [
                        dcc.Graph(figure=fig_ocupacao, style={"flex": "1", "minWidth": "300px"}),
                    ],
                    style={"display": "flex", "gap": "24px", "flexWrap": "wrap"},
                ),

                
            ]
        )


    elif tab == 'tab-alunos':
        df_alunos = get_alunos_dataframe()
        if df_alunos.empty:
            return html.Div('Sem alunos/assistidos cadastrados.')

        df_frequentando = df_alunos[df_alunos['status_lsd'] == 'Frequentando'].copy()

        total = len(df_alunos)
        frequentando = len(df_frequentando)
        meninas = len(df_frequentando[df_frequentando['sex'] == 'Feminino'])
        meninos = len(df_frequentando[df_frequentando['sex'] == 'Masculino'])
        criancas = len(df_frequentando[df_frequentando['idade'].between(6, 12)])
        adolescentes = len(df_frequentando[df_frequentando['idade'].between(13, 17)])

        publico_counts = (
            df_frequentando['publico_dashboard']
            .value_counts()
            .reindex(['Crianças (6 a 12 anos)', 'Adolescentes (13 a 17 anos)'])
            .fillna(0)
            .reset_index()
        )
        publico_counts.columns = ['publico', 'qtd']
        fig_publico = criar_fig_bar(
            publico_counts, 'publico', 'qtd', 'Assistidos por público', 'Público', 'Quantidade de assistidos'
        )

        alunos_rede_counts = (
            df_frequentando['rede_ensino']
            .fillna('Não informado')
            .value_counts()
            .reset_index()
        )
        alunos_rede_counts.columns = ['rede_ensino', 'qtd']
        fig_rede = criar_fig_bar(
            alunos_rede_counts, 'rede_ensino', 'qtd', 'Alunos por rede de ensino', 'Rede de ensino', 'Quantidade de alunos'
        )

        turno_counts = (
            df_frequentando['turno']
            .fillna('Não informado')
            .value_counts()
            .reset_index()
        )
        turno_counts.columns = ['turno', 'qtd']
        fig_turno = criar_fig_bar(
            turno_counts, 'turno', 'qtd', 'Alunos por turno', 'Turno', 'Quantidade de alunos'
        )

        escola_counts = (
            df_frequentando['school']
            .fillna('Não informado')
            .astype(str)
            .str.strip()
            .value_counts()
            .reset_index()
        )
        escola_counts.columns = ['escola', 'qtd']
        top_escolas = escola_counts.head(15)
        fig_escola = criar_fig_bar(
            top_escolas, 'escola', 'qtd', 'Alunos por escola (Top 15)', 'Quantidade de alunos', 'Escola', orientation='h'
        )

        kpi_cards = dbc.Row(
            [
                dbc.Col(dbc.Card(dbc.CardBody([
                    html.H6('Crianças/Adolescentes cadastrados', className='text-muted mb-2 text-center'),
                    html.H3(f'{total}', className='mb-0 text-center'),
                ]), className='mb-3 shadow-sm'), md=2),
                dbc.Col(dbc.Card(dbc.CardBody([
                    html.H6('Assistidos frequentando', className='text-muted mb-2 text-center'),
                    html.H3(f'{frequentando}', className='mb-0 text-success text-center'),
                ]), className='shadow-sm'), md=2),
                dbc.Col(dbc.Card(dbc.CardBody([
                    html.H6('Crianças (6 a 12 anos)', className='text-muted mb-2 text-center'),
                    html.H3(f'{criancas}', className='mb-0 text-primary text-center'),
                ]), className='shadow-sm'), md=2),
                dbc.Col(dbc.Card(dbc.CardBody([
                    html.H6('Adolescentes (13 a 17 anos)', className='text-muted mb-2 text-center'),
                    html.H3(f'{adolescentes}', className='mb-0 text-warning text-center'),
                ]), className='shadow-sm'), md=2),
                dbc.Col(dbc.Card(dbc.CardBody([
                    html.H6('Meninas', className='text-muted mb-2 text-center'),
                    html.H3(f'{meninas}', className='mb-0 text-danger text-center'),
                ]), className='shadow-sm'), md=2),
                dbc.Col(dbc.Card(dbc.CardBody([
                    html.H6('Meninos', className='text-muted mb-2 text-center'),
                    html.H3(f'{meninos}', className='mb-0 text-info text-center'),
                ]), className='shadow-sm'), md=2),
            ],
            className='mb-4 g-3',
        )

        return html.Div([
            kpi_cards,
            html.Div([
                dcc.Graph(figure=fig_publico, style={'flex': '1', 'minWidth': '300px'}),
                dcc.Graph(figure=fig_rede, style={'flex': '1', 'minWidth': '300px'}),
            ], style={'display': 'flex', 'gap': '24px', 'flexWrap': 'wrap'}),
            html.Div([
                dcc.Graph(figure=fig_turno, style={'flex': '1', 'minWidth': '300px'}),
                dcc.Graph(figure=fig_escola, style={'flex': '1', 'minWidth': '300px'}),
            ], style={'display': 'flex', 'gap': '24px', 'flexWrap': 'wrap'}),
        ])

    elif tab == 'tab-idosos':
        df_idosos = get_adult_dataframe()
        if df_idosos.empty:
            return html.Div('Sem idosos cadastrados.')

        if 'status_lsd' in df_idosos.columns:
            df_idosos_ativos = df_idosos[df_idosos['status_lsd'] == 'Frequentando'].copy()
            if df_idosos_ativos.empty:
                df_idosos_ativos = df_idosos.copy()
        else:
            df_idosos_ativos = df_idosos.copy()

        total_idosos = len(df_idosos)
        idosos_ativos = len(df_idosos_ativos)
        idosas = len(df_idosos_ativos[df_idosos_ativos['sex'] == 'Feminino'])
        idosos_homens = len(df_idosos_ativos[df_idosos_ativos['sex'] == 'Masculino'])
        idosos_60_69 = len(df_idosos_ativos[df_idosos_ativos['idade'].between(60, 69)])
        idosos_70_mais = len(df_idosos_ativos[df_idosos_ativos['idade'] >= 70])

        sexo_counts = df_idosos_ativos['sex'].fillna('Não informado').value_counts().reset_index()
        sexo_counts.columns = ['sexo', 'qtd']
        fig_idosos_sexo = criar_fig_bar(
            sexo_counts, 'sexo', 'qtd', 'Idosos por sexo', 'Sexo', 'Quantidade de idosos'
        )

        faixa_counts = (
            df_idosos_ativos['faixa_etaria_idosos']
            .value_counts()
            .reindex(['60-69', '70-79', '80-89', '90+'])
            .fillna(0)
            .reset_index()
        )
        faixa_counts.columns = ['faixa', 'qtd']
        fig_idosos_faixa = criar_fig_bar(
            faixa_counts, 'faixa', 'qtd', 'Idosos por faixa etária', 'Faixa etária', 'Quantidade de idosos'
        )

        kpi_cards = dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6('Idosos cadastrados', className='text-muted mb-2 text-center'),
                html.H3(f'{total_idosos}', className='mb-0 text-center'),
            ]), className='shadow-sm'), md=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6('Idosos assistidos', className='text-muted mb-2 text-center'),
                html.H3(f'{idosos_ativos}', className='mb-0 text-success text-center'),
            ]), className='shadow-sm'), md=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6('Faixa 60 a 69 anos', className='text-muted mb-2 text-center'),
                html.H3(f'{idosos_60_69}', className='mb-0 text-primary text-center'),
            ]), className='shadow-sm'), md=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6('Faixa 70 anos ou mais', className='text-muted mb-2 text-center'),
                html.H3(f'{idosos_70_mais}', className='mb-0 text-warning text-center'),
            ]), className='shadow-sm'), md=3),
        ], className='mb-4 g-3')

        return html.Div([
            kpi_cards,
            html.Div([
                dcc.Graph(figure=fig_idosos_sexo, style={'flex': '1', 'minWidth': '300px'}),
                dcc.Graph(figure=fig_idosos_faixa, style={'flex': '1', 'minWidth': '300px'}),
            ], style={'display': 'flex', 'gap': '24px', 'flexWrap': 'wrap'}),
            html.Div([
                dbc.Card(dbc.CardBody([
                    html.H6('Detalhamento rápido', className='text-muted mb-2'),
                    html.P(f'Idosas: {idosas} | Idosos: {idosos_homens}', className='mb-0'),
                ]), className='shadow-sm')
            ], className='mt-2'),
        ])

    elif tab == 'tab-turmas':
        df_turmas = get_turmas_dataframe()
        df_alunos = get_alunos_dataframe()

        if df_turmas.empty:
            return html.Div('Sem turmas cadastradas.')

        total_turmas = len(df_turmas)
        turmas_ativas = len(df_turmas[df_turmas['status'] == 'ativo']) if 'status' in df_turmas.columns else total_turmas
        turnos = len(df_turmas['turno'].dropna().unique()) if 'turno' in df_turmas.columns else 0
        educadores = len(df_turmas['educatora__name'].dropna().unique()) if 'educatora__name' in df_turmas.columns else 0

        turno_counts = df_turmas['turno'].fillna('Não informado').value_counts().reset_index()
        turno_counts.columns = ['turno', 'qtd']
        fig_turmas_turno = criar_fig_bar(
            turno_counts, 'turno', 'qtd', 'Turmas por turno', 'Turno', 'Quantidade de turmas'
        )

        educador_counts = (
            df_turmas['educatora__name']
            .fillna('Não informado')
            .value_counts()
            .reset_index()
        )
        educador_counts.columns = ['educador', 'qtd']
        fig_turmas_educador = criar_fig_bar(
            educador_counts, 'educador', 'qtd', 'Turmas por educador', 'Quantidade de turmas', 'Educador', orientation='h'
        )

        if not df_alunos.empty and 'status_lsd' in df_alunos.columns:
            df_frequentando = df_alunos[df_alunos['status_lsd'] == 'Frequentando'].copy()
            publico_counts = (
                df_frequentando['publico_dashboard']
                .value_counts()
                .reindex(['Crianças (6 a 12 anos)', 'Adolescentes (13 a 17 anos)'])
                .fillna(0)
                .reset_index()
            )
            publico_counts.columns = ['publico', 'qtd']
            fig_turmas_publico = criar_fig_bar(
                publico_counts, 'publico', 'qtd', 'Público atendido nas turmas', 'Público', 'Quantidade de assistidos'
            )
        else:
            fig_turmas_publico = px.bar(title='Público atendido nas turmas')

        kpi_cards = dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6('Turmas cadastradas', className='text-muted mb-2 text-center'),
                html.H3(f'{total_turmas}', className='mb-0 text-center'),
            ]), className='shadow-sm'), md=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6('Turmas ativas', className='text-muted mb-2 text-center'),
                html.H3(f'{turmas_ativas}', className='mb-0 text-success text-center'),
            ]), className='shadow-sm'), md=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6('Turnos com turmas', className='text-muted mb-2 text-center'),
                html.H3(f'{turnos}', className='mb-0 text-primary text-center'),
            ]), className='shadow-sm'), md=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6('Educadores vinculados', className='text-muted mb-2 text-center'),
                html.H3(f'{educadores}', className='mb-0 text-warning text-center'),
            ]), className='shadow-sm'), md=3),
        ], className='mb-4 g-3')

        return html.Div([
            kpi_cards,
            html.Div([
                dcc.Graph(figure=fig_turmas_turno, style={'flex': '1', 'minWidth': '300px'}),
                dcc.Graph(figure=fig_turmas_publico, style={'flex': '1', 'minWidth': '300px'}),
            ], style={'display': 'flex', 'gap': '24px', 'flexWrap': 'wrap'}),
            dcc.Graph(figure=fig_turmas_educador),
        ])

    elif tab == 'tab-atividades':
        df_atividades = get_activities_dataframe()
        df_alunos = get_alunos_dataframe()
        df_idosos = get_adult_dataframe()

        if df_atividades.empty:
            return html.Div('Sem atividades cadastradas.')

        total_atividades = len(df_atividades)
        atividades_ativas = len(df_atividades[df_atividades['status'] == 'ativo']) if 'status' in df_atividades.columns else total_atividades
        publico_criancas = 0
        publico_adolescentes = 0
        publico_idosos = 0

        if not df_alunos.empty:
            df_frequentando = df_alunos[df_alunos['status_lsd'] == 'Frequentando'].copy()
            publico_criancas = len(df_frequentando[df_frequentando['idade'].between(6, 12)])
            publico_adolescentes = len(df_frequentando[df_frequentando['idade'].between(13, 17)])

        if not df_idosos.empty:
            if 'status_lsd' in df_idosos.columns:
                df_idosos_ativos = df_idosos[df_idosos['status_lsd'] == 'Frequentando'].copy()
                if df_idosos_ativos.empty:
                    df_idosos_ativos = df_idosos.copy()
            else:
                df_idosos_ativos = df_idosos.copy()
            publico_idosos = len(df_idosos_ativos)

        status_counts = df_atividades['status'].fillna('Não informado').value_counts().reset_index() if 'status' in df_atividades.columns else pd.DataFrame({'status': ['Sem status'], 'qtd': [total_atividades]})
        if 'status' in status_counts.columns:
            status_counts.columns = ['status', 'qtd']
        fig_atividades_status = criar_fig_bar(
            status_counts, 'status', 'qtd', 'Atividades por status', 'Status', 'Quantidade de atividades'
        )

        publico_df = pd.DataFrame({
            'publico': ['Crianças (6 a 12 anos)', 'Adolescentes (13 a 17 anos)', 'Idosos'],
            'qtd': [publico_criancas, publico_adolescentes, publico_idosos]
        })
        fig_atividades_publico = criar_fig_bar(
            publico_df, 'publico', 'qtd', 'Público vinculado às atividades', 'Público', 'Quantidade de assistidos'
        )

        nome_counts = df_atividades['name'].fillna('Não informado').value_counts().reset_index().head(15)
        nome_counts.columns = ['atividade', 'qtd']
        fig_atividades_nome = criar_fig_bar(
            nome_counts, 'atividade', 'qtd', 'Atividades cadastradas', 'Quantidade', 'Atividade', orientation='h'
        )

        kpi_cards = dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6('Atividades cadastradas', className='text-muted mb-2 text-center'),
                html.H3(f'{total_atividades}', className='mb-0 text-center'),
            ]), className='shadow-sm'), md=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6('Atividades ativas', className='text-muted mb-2 text-center'),
                html.H3(f'{atividades_ativas}', className='mb-0 text-success text-center'),
            ]), className='shadow-sm'), md=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6('Público infantil', className='text-muted mb-2 text-center'),
                html.H3(f'{publico_criancas}', className='mb-0 text-primary text-center'),
            ]), className='shadow-sm'), md=3),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6('Público adolescente', className='text-muted mb-2 text-center'),
                html.H3(f'{publico_adolescentes}', className='mb-0 text-warning text-center'),
            ]), className='shadow-sm'), md=3),
        ], className='mb-4 g-3')

        return html.Div([
            kpi_cards,
            html.Div([
                dcc.Graph(figure=fig_atividades_status, style={'flex': '1', 'minWidth': '300px'}),
                dcc.Graph(figure=fig_atividades_publico, style={'flex': '1', 'minWidth': '300px'}),
            ], style={'display': 'flex', 'gap': '24px', 'flexWrap': 'wrap'}),
            dcc.Graph(figure=fig_atividades_nome),
        ])

    else:
        return html.Div('Em construção.')
