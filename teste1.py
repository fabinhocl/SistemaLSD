import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

connection_url = URL.create(
    drivername="postgresql+psycopg2",
    username="lsd_user",
    password="Sys.Admin!@#098",
    host="localhost",
    port=5432,
    database="lsd"
)

engine = create_engine(connection_url)



sql_cols_usuarios = text("""
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND (
      table_name ILIKE '%user%'
      OR table_name ILIKE '%usuario%'
      OR table_name ILIKE '%pessoa%'
      OR table_name ILIKE '%educadora%'
  )
ORDER BY table_name, ordinal_position
""")

with engine.connect() as conn:
    print(pd.read_sql(sql_cols_usuarios, conn))