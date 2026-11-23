import os
import json
import logging
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.models import Base, Cidade, Feriado, MedicaoClimatica

load_dotenv()
logger = logging.getLogger(__name__)

DIAS_SEMANA_PT = [
    "Segunda-feira",
    "Terça-feira",
    "Quarta-feira",
    "Quinta-feira",
    "Sexta-feira",
    "Sábado",
    "Domingo",
]

MAPA_UF_CAPITAIS = {
    "Rio Branco": "AC", "Maceió": "AL", "Maceio": "AL", "Macapá": "AP", "Macapa": "AP",
    "Manaus": "AM", "Salvador": "BA", "Fortaleza": "CE", "Brasília": "DF", "Brasilia": "DF",
    "Vitória": "ES", "Vitoria": "ES", "Goiânia": "GO", "Goiania": "GO",
    "São Luís": "MA", "Sao Luis": "MA", "Cuiabá": "MT", "Cuiaba": "MT",
    "Campo Grande": "MS", "Belo Horizonte": "MG", "Belém": "PA", "Belem": "PA",
    "João Pessoa": "PB", "Joao Pessoa": "PB", "Curitiba": "PR", "Recife": "PE",
    "Teresina": "PI", "Rio de Janeiro": "RJ", "Natal": "RN", "Porto Alegre": "RS",
    "Porto Velho": "RO", "Boa Vista": "RR", "Florianópolis": "SC", "Florianopolis": "SC",
    "São Paulo": "SP", "Sao Paulo": "SP", "Aracaju": "SE", "Palmas": "TO"
}


def carregar_para_postgres(df_gold: pd.DataFrame, caminho_feriados_json: str) -> None:
    """
    Cria as tabelas no PostgreSQL e realiza a carga idempotente (Upsert) dos dados.
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("Variável DATABASE_URL não encontrada no arquivo .env")

    engine = create_engine(database_url)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 1. Upsert dos feriados nacionais
        with open(caminho_feriados_json, "r", encoding="utf-8") as f:
            feriados_raw = json.load(f)

        for item in feriados_raw:
            data_obj = datetime.strptime(item["date"], "%Y-%m-%d").date()
            dia_semana_nome = DIAS_SEMANA_PT[data_obj.weekday()]

            stmt_feriado = pg_insert(Feriado).values(
                data=data_obj,
                nome=item["name"],
                tipo=item["type"],
                dia_semana=dia_semana_nome
            ).on_conflict_do_update(
                index_elements=["data"],
                set_={
                    "nome": item["name"],
                    "tipo": item["type"],
                    "dia_semana": dia_semana_nome
                }
            )
            session.execute(stmt_feriado)

        # 2. Upsert das cidades e mapeamento nome -> id
        cidades_unicas = df_gold["cidade"].unique()
        for nome_cidade in cidades_unicas:
            uf_cidade = MAPA_UF_CAPITAIS.get(nome_cidade)
            stmt_cidade = pg_insert(Cidade).values(
                nome=nome_cidade,
                uf=uf_cidade
            ).on_conflict_do_update(
                index_elements=["nome"],
                set_={"uf": uf_cidade}
            )
            session.execute(stmt_cidade)

        session.commit()

        mapa_cidades = {c.nome: c.id for c in session.query(Cidade).all()}

        # 3. Upsert das medições climáticas
        for _, row in df_gold.iterrows():
            cidade_id = mapa_cidades[row["cidade"]]
            stmt_medicao = pg_insert(MedicaoClimatica).values(
                cidade_id=cidade_id,
                data=row["data"],
                temperatura_c=float(row["temperatura_c"]),
                sensacao_termica_c=float(row["sensacao_termica_c"]),
                amplitude_termica_c=float(row["amplitude_termica_c"]),
                umidade_percent=int(row["umidade_percent"]),
                descricao_clima=row["descricao_clima"],
                classificacao_termica=row["classificacao_termica"],
            ).on_conflict_do_update(
                constraint="uq_cidade_data",
                set_={
                    "temperatura_c": float(row["temperatura_c"]),
                    "sensacao_termica_c": float(row["sensacao_termica_c"]),
                    "amplitude_termica_c": float(row["amplitude_termica_c"]),
                    "umidade_percent": int(row["umidade_percent"]),
                    "descricao_clima": row["descricao_clima"],
                    "classificacao_termica": row["classificacao_termica"],
                }
            )
            session.execute(stmt_medicao)

        session.commit()
        logger.info(f"Carga no PostgreSQL concluída com sucesso ({len(df_gold)} medições sincronizadas).")

    except Exception as e:
        session.rollback()
        logger.error(f"Erro ao persistir dados no PostgreSQL: {e}")
        raise
    finally:
        session.close()