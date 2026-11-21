import duckdb
import pandas as pd


def transformar_dados_sql(caminho_clima_json: str, caminho_feriados_json: str) -> pd.DataFrame:
    """
    Executa desaninhamento duplo (UNNEST de 'list' e 'weather') e agregação diária via DuckDB SQL.
    """
    con = duckdb.connect(database=":memory:")

    query = f"""
    WITH raw_clima AS (
        SELECT * FROM read_json_auto('{caminho_clima_json}')
    ),
    -- 1. PRIMEIRO UNNEST: Explode a lista de 40 previsões (5 dias x 8 horários) por cidade
    previsoes_explodidas AS (
        SELECT
            CAST(city.name AS VARCHAR) AS cidade,
            UNNEST(list) AS item
        FROM raw_clima
    ),
    -- 2. SEGUNDO UNNEST: Explode o array 'weather' de cada previsão
    clima_desaninhado AS (
        SELECT
            cidade,
            CAST(to_timestamp(item.dt) AS DATE) AS data,
            CAST(item.main.temp AS DOUBLE) AS temperatura_c,
            CAST(item.main.feels_like AS DOUBLE) AS sensacao_termica_c,
            CAST(item.main.temp_min AS DOUBLE) AS temp_min_c,
            CAST(item.main.temp_max AS DOUBLE) AS temp_max_c,
            CAST(item.main.humidity AS INTEGER) AS umidade_percent,
            w.unnest.description AS descricao_clima
        FROM previsoes_explodidas,
        UNNEST(item.weather) AS w
    ),
    -- 3. DEDUPLICAÇÃO E AGREGAÇÃO DIÁRIA (1 registro consolidado por cidade + dia)
    clima_diario AS (
        SELECT
            TRIM(cidade) AS cidade,
            data,
            EXTRACT(YEAR FROM data)::INTEGER AS ano,
            EXTRACT(MONTH FROM data)::INTEGER AS mes,
            ROUND(AVG(temperatura_c), 2) AS temperatura_c,
            ROUND(AVG(sensacao_termica_c), 2) AS sensacao_termica_c,
            ROUND(MIN(temp_min_c), 2) AS temp_min_c,
            ROUND(MAX(temp_max_c), 2) AS temp_max_c,
            ROUND(AVG(umidade_percent))::INTEGER AS umidade_percent,
            COALESCE(FIRST(descricao_clima), 'Não informado') AS descricao_clima
        FROM clima_desaninhado
        WHERE data IS NOT NULL AND cidade IS NOT NULL
        GROUP BY TRIM(cidade), data
    ),
    raw_feriados AS (
        SELECT
            CAST(date AS DATE) AS data_feriado,
            CAST(name AS VARCHAR) AS nome_feriado,
            CAST(type AS VARCHAR) AS tipo_feriado
        FROM read_json_auto('{caminho_feriados_json}')
    )
    -- 4. CRUZAMENTO DE FONTES (LEFT JOIN), TRATAMENTO DE NULOS E ENRIQUECIMENTO DE MÉTRICAS
    SELECT
        c.cidade,
        c.data,
        c.ano,
        c.mes,
        CASE WHEN f.data_feriado IS NOT NULL THEN TRUE ELSE FALSE END AS eh_feriado,
        COALESCE(f.nome_feriado, 'Sem feriado nacional') AS nome_feriado,
        COALESCE(f.tipo_feriado, 'dia_comum') AS tipo_feriado,
        c.temperatura_c,
        c.sensacao_termica_c,
        c.umidade_percent,
        c.descricao_clima,
        ROUND(c.temp_max_c - c.temp_min_c, 2) AS amplitude_termica_c,
        ROUND(c.sensacao_termica_c - c.temperatura_c, 2) AS indice_desconforto_termico,
        CASE
            WHEN c.temperatura_c >= 30.0 THEN 'Calor Intenso'
            WHEN c.temperatura_c >= 20.0 THEN 'Agradável'
            ELSE 'Frio / Ameno'
        END AS classificacao_termica
    FROM clima_diario c
    LEFT JOIN raw_feriados f
        ON c.data = f.data_feriado
    ORDER BY c.cidade, c.data
    """

    df_final = con.execute(query).df()
    con.close()
    return df_final