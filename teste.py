import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.styles.numbers import FORMAT_PERCENTAGE_00

connection_url = URL.create(
    drivername="postgresql+psycopg2",
    username="lsd_user",
    password="Sys.Admin!@#098",
    host="localhost",
    port=5432,
    database="lsd"
)


engine = create_engine(connection_url)

sql = text("""
WITH freq_mes AS (
    SELECT
        fa."aluno_id" AS aluno_id,
        date_trunc('month', ft."data")::date AS mes_ref,
        COUNT(*) AS total_chamadas,
        SUM(CASE WHEN fa."presente" = true THEN 1 ELSE 0 END) AS total_presencas,
        SUM(CASE WHEN fa."presente" = false THEN 1 ELSE 0 END) AS total_faltas
    FROM "AppLSD_frequenciaaluno" fa
    JOIN "AppLSD_frequenciaturma" ft
        ON ft."id" = fa."chamada_id"
    WHERE ft."data" >= :data_inicio
      AND ft."data" < :data_fim
      AND COALESCE(ft."excluido", false) = false
      AND COALESCE(fa."presente", false) IN (true, false)
    GROUP BY fa."aluno_id", date_trunc('month', ft."data")::date
)
SELECT
    f."responsible_name" AS familia,
    f."telephone",
    CONCAT_WS(', ',
        f."address",
        f."number",
        f."neighborhood",
        f."reference_point"
    ) AS endereco_completo,
    a."name" AS assistido,
    a."status_lsd",
    CONCAT_WS(' - ',
        NULLIF(t."grupo", ''),
        NULLIF(t."turno", ''),
        NULLIF(t."faixa_etaria", '')
    ) AS turma,
    CONCAT_WS(' ', u."first_name", u."last_name") AS educadora,       
    fm.mes_ref,
    COALESCE(fm.total_chamadas, 0) AS total_chamadas,
    COALESCE(fm.total_presencas, 0) AS total_presencas,
    COALESCE(fm.total_faltas, 0) AS total_faltas,
    COALESCE(
        ROUND((fm.total_presencas::numeric / NULLIF(fm.total_chamadas, 0)) * 100, 2),
        0
    ) AS percentual_presencas
FROM "AppLSD_aluno" a
JOIN "AppLSD_family" f
    ON a."family_id" = f."id"
LEFT JOIN freq_mes fm
    ON fm.aluno_id = a."id"
LEFT JOIN "AppLSD_turma" t
    ON a."turma_id" = t."id"
LEFT JOIN "auth_user" u
    ON t."educadora_id" = u."id"
WHERE LOWER(a."status_lsd") = 'frequentando'
  AND COALESCE(a."excluido", false) = false
  AND COALESCE(f."excluido", false) = false
ORDER BY f."responsible_name", a."name", fm.mes_ref
""")

params = {
    "data_inicio": "2026-04-01",
    "data_fim": "2026-05-01"
}

with engine.connect() as conn:
    df = pd.read_sql(sql, conn, params=params)

df = df.sort_values(["familia", "assistido", "mes_ref"], na_position="last")

consolidado = (
    df.groupby(["familia", "telephone", "endereco_completo"], dropna=False, as_index=False)
      .agg(
          assistidos=("assistido", lambda x: " | ".join(sorted(set(v for v in x if pd.notna(v))))),
          total_chamadas=("total_chamadas", "sum"),
          total_presencas=("total_presencas", "sum"),
          total_faltas=("total_faltas", "sum")
      )
)

consolidado["percentual_presencas"] = (
    consolidado["total_presencas"] / consolidado["total_chamadas"]
).fillna(0).round(4)

with pd.ExcelWriter("relatorio_frequencia_maio.xlsx", engine="openpyxl") as writer:
    df.to_excel(writer, index=False, sheet_name="Detalhado")
    consolidado.to_excel(writer, index=False, sheet_name="Familia")

df.to_csv("relatorio_frequencia_maio.csv", index=False, sep=";", encoding="utf-8-sig")
print("Arquivos gerados com sucesso.")