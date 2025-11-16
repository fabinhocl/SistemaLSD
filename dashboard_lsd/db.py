import sqlite3
import pandas as pd

DB_PATH = 'lsd.sqlite'

def query_db(query, params=()):
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(query, con, params=params)
    con.close()
    return df

def get_familias():
    return query_db("SELECT * FROM family")

def get_assistidos():
    return query_db("SELECT * FROM alunos")

def get_presencas_by_dia(dia):
    return query_db("SELECT * FROM presencas WHERE data=?", [dia])
