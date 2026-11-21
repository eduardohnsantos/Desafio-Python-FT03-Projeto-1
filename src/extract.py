import os
import json
import logging
import requests
from dotenv import load_dotenv
from ratelimit import limits, sleep_and_retry
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
from src.schema import FeriadoSchema, ClimaSchema

CAPITAIS_BRASIL = [
    "Rio Branco,AC,BR",
    "Maceio,AL,BR",
    "Macapa,AP,BR",
    "Manaus,AM,BR",
    "Salvador,BA,BR",
    "Fortaleza,CE,BR",
    "Brasilia,DF,BR",
    "Vitoria,ES,BR",
    "Goiania,GO,BR",
    "Sao Luis,MA,BR",
    "Cuiaba,MT,BR",
    "Campo Grande,MS,BR",
    "Belo Horizonte,MG,BR",
    "Belem,PA,BR",
    "Joao Pessoa,PB,BR",
    "Curitiba,PR,BR",
    "Recife,PE,BR",
    "Teresina,PI,BR",
    "Rio de Janeiro,RJ,BR",
    "Natal,RN,BR",
    "Porto Alegre,RS,BR",
    "Porto Velho,RO,BR",
    "Boa Vista,RR,BR",
    "Florianopolis,SC,BR",
    "Sao Paulo,SP,BR",
    "Aracaju,SE,BR",
    "Palmas,TO,BR"
]

load_dotenv()
logger = logging.getLogger(__name__)

BRASIL_API_URL = os.getenv("BRASIL_API_URL", "https://brasilapi.com.br/api")
OPENWEATHER_API_URL = os.getenv("OPENWEATHER_API_URL", "https://api.openweathermap.org/data/2.5/forecast")
WEATHER_KEY = os.getenv("WEATHER_KEY")


@sleep_and_retry
@limits(calls=5, period=10)
@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.exceptions.RequestException,)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)
def extrair_feriados_raw(ano: int, caminho_saida: str = "data/raw/feriados.json") -> list[dict]:
    """Extrai feriados da BrasilAPI, valida com Pydantic e salva o JSON bruto."""
    url = f"{BRASIL_API_URL.rstrip('/')}/feriados/v1/{ano}"
    logger.info(f"Extraindo feriados de {ano} na BrasilAPI...")
    
    response = requests.get(url=url, timeout=10)
    response.raise_for_status()
    dados_brutos = response.json()

    # Validação de entrada com Pydantic
    for item in dados_brutos:
        FeriadoSchema.model_validate(item)

    os.makedirs(os.path.dirname(caminho_saida), exist_ok=True)
    with open(caminho_saida, "w", encoding="utf-8") as f:
        json.dump(dados_brutos, f, ensure_ascii=False, indent=4)

    logger.info(f"Feriados salvos com sucesso em {caminho_saida}")
    return dados_brutos


@sleep_and_retry
@limits(calls=5, period=10)
@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.exceptions.RequestException,)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)
def extrair_climas_raw(cidades: list[str], caminho_saida: str = "data/raw/clima.json") -> list[dict]:
    """Extrai clima atual de uma lista de cidades na OpenWeather, valida com Pydantic e salva JSON bruto."""
    if not WEATHER_KEY:
        raise EnvironmentError("WEATHER_KEY não encontrada no arquivo .env")

    resultados_brutos = []
    for cidade in cidades:
        params = {
            "q": cidade,
            "appid": WEATHER_KEY,
            "units": "metric",
            "lang": "pt_br"
        }
        logger.info(f"Extraindo clima de {cidade} na OpenWeather...")
        response = requests.get(url=OPENWEATHER_API_URL, params=params, timeout=10)
        response.raise_for_status()
        dado_cidade = response.json()

        # Validação de entrada com Pydantic
        ClimaSchema.model_validate(dado_cidade)
        resultados_brutos.append(dado_cidade)

    os.makedirs(os.path.dirname(caminho_saida), exist_ok=True)
    with open(caminho_saida, "w", encoding="utf-8") as f:
        json.dump(resultados_brutos, f, ensure_ascii=False, indent=4)

    logger.info(f"Dados climáticos de {len(resultados_brutos)} cidades salvos em {caminho_saida}")
    return resultados_brutos