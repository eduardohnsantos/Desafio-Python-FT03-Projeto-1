import logging
from datetime import datetime
from src.extract import extrair_feriados_raw, extrair_climas_raw
from src.transform import transformar_dados_sql
from src.quality import validar_e_persistir

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def executar_pipeline() -> None:
    ano_atual = datetime.now().year
    CAPITAIS_BRASIL = [
    "Rio Branco,AC,BR", "Maceio,AL,BR", "Macapa,AP,BR", "Manaus,AM,BR",
    "Salvador,BA,BR", "Fortaleza,CE,BR", "Brasilia,DF,BR", "Vitoria,ES,BR",
    "Goiania,GO,BR", "Sao Luis,MA,BR", "Cuiaba,MT,BR", "Campo Grande,MS,BR",
    "Belo Horizonte,MG,BR", "Belem,PA,BR", "Joao Pessoa,PB,BR", "Curitiba,PR,BR",
    "Recife,PE,BR", "Teresina,PI,BR", "Rio de Janeiro,RJ,BR", "Natal,RN,BR",
    "Porto Alegre,RS,BR", "Porto Velho,RO,BR", "Boa Vista,RR,BR",
    "Florianopolis,SC,BR", "Sao Paulo,SP,BR", "Aracaju,SE,BR", "Palmas,TO,BR"
]

    caminho_feriados = "data/raw/feriados.json"
    caminho_clima = "data/raw/clima.json"

    logger.info("=== INICIANDO PIPELINE ===")

    # Etapa 1: Extração + Validação Pydantic (Camada Raw)
    extrair_feriados_raw(ano=ano_atual, caminho_saida=caminho_feriados)
    extrair_climas_raw(cidades=CAPITAIS_BRASIL, caminho_saida=caminho_clima)

    # Etapa 2: Transformação SQL via DuckDB (UNNEST, JOIN, Deduplicação, Métricas)
    logger.info("Executando transformações SQL e cruzamento de fontes via DuckDB...")
    df_transformado = transformar_dados_sql(
        caminho_clima_json=caminho_clima,
        caminho_feriados_json=caminho_feriados
    )
    print("\n--- Prévia da Tabela Consolidada ---")
    print(df_transformado[["cidade", "data", "eh_feriado", "nome_feriado", "temperatura_c", "classificacao_termica"]])

    # Etapa 3: Data Quality + Exportação Relatório JSON + Parquet Particionado (Snappy)
    logger.info("Executando auditoria de Data Quality e gravando camada Gold em Parquet...")
    relatorio = validar_e_persistir(df=df_transformado)

    from src.load_db import carregar_para_postgres

    carregar_para_postgres(df_gold=df_transformado, caminho_feriados_json=caminho_feriados)

    logger.info(f"=== PIPELINE CONCLUÍDO COM STATUS: {relatorio['status']} ===")


if __name__ == "__main__":
    executar_pipeline()