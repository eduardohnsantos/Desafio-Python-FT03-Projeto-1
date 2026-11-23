import os
import json
from datetime import datetime, timezone
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


def validar_e_persistir(
    df: pd.DataFrame,
    caminho_parquet: str = "output/clima_feriados",
    caminho_relatorio: str = "output/data_quality_report.json"
) -> dict:
    """
    Valida a qualidade dos dados, exporta o relatório JSON e salva o dataset em Parquet particionado.
    """
    os.makedirs(os.path.dirname(caminho_relatorio), exist_ok=True)
    os.makedirs(caminho_parquet, exist_ok=True)

    # 1. Validação das colunas obrigatórias
    colunas_esperadas = {
        "cidade", "data", "ano", "mes", "eh_feriado", "nome_feriado",
        "tipo_feriado", "temperatura_c", "umidade_percent", "amplitude_termica_c"
    }
    colunas_faltantes = list(colunas_esperadas - set(df.columns))
    schema_valido = len(colunas_faltantes) == 0

    # 2. Proporção de nulos por coluna
    null_ratios = {
        col: round(float(df[col].isna().mean()), 4)
        for col in df.columns
    }

    # 3. Verificação de duplicidade (cidade + data)
    total_linhas = len(df)
    linhas_unicas = len(df.drop_duplicates(subset=["cidade", "data"]))
    duplicatas = total_linhas - linhas_unicas
    unicidade_ok = duplicatas == 0

    # 4. Validação de faixas físicas (temperatura e umidade)
    temp_fora_intervalo = int(((df["temperatura_c"] < -50) | (df["temperatura_c"] > 60)).sum())
    umidade_fora_intervalo = int(((df["umidade_percent"] < 0) | (df["umidade_percent"] > 100)).sum())
    intervalos_ok = (temp_fora_intervalo == 0) and (umidade_fora_intervalo == 0)

    status_geral = "PASSED" if (schema_valido and unicidade_ok and intervalos_ok and total_linhas > 0) else "FAILED"

    # 5. Geração e exportação do relatório JSON
    relatorio = {
        "timestamp_execucao": datetime.now(timezone.utc).isoformat(),
        "status": status_geral,
        "metricas_gerais": {
            "total_registros": total_linhas,
            "registros_unicos": linhas_unicas,
            "duplicatas_encontradas": duplicatas
        },
        "validacoes": {
            "schema_valido": schema_valido,
            "colunas_faltantes": colunas_faltantes,
            "unicidade_ok": unicidade_ok,
            "intervalos_ok": intervalos_ok,
            "erros_intervalo_temperatura": temp_fora_intervalo,
            "erros_intervalo_umidade": umidade_fora_intervalo
        },
        "null_ratio_por_coluna": null_ratios
    }

    with open(caminho_relatorio, "w", encoding="utf-8") as f:
        json.dump(relatorio, f, ensure_ascii=False, indent=4)

    if status_geral != "PASSED":
        raise ValueError(f"Pipeline bloqueado pelo Data Quality! Verifique {caminho_relatorio}")

    # 6. Gravação em Parquet particionado (ano/mes) com compressão Snappy
    tabela_arrow = pa.Table.from_pandas(df)
    pq.write_to_dataset(
        tabela_arrow,
        root_path=caminho_parquet,
        partition_cols=["ano", "mes"],
        compression="snappy"
    )

    return relatorio