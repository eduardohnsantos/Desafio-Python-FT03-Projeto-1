import os
import logging
from datetime import date
from typing import Optional
import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator
from ratelimit import limits, sleep_and_retry
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()
BRASIL_API_URL = os.getenv("BRASIL_API_URL", "https://brasilapi.com.br/api")

DIA_DA_SEMANA = {
    0: "Segunda-feira",
    1: "Terça-feira",
    2: "Quarta-feira",
    3: "Quinta-feira",
    4: "Sexta-feira",
    5: "Sábado",
    6: "Domingo"
}

class FeriadoSchema(BaseModel):
    data: date = Field(alias="date")          
    nome: str = Field(alias="name")
    tipo: str = Field(alias="type")
    dia_semana: Optional[str] = Field(default=None, alias="weekday")


    @model_validator(mode="after")
    def preencher_dia_semana(self) -> "FeriadoSchema":
        if not self.dia_semana:
            self.dia_semana = DIA_DA_SEMANA[self.data.weekday()]
        return self


@sleep_and_retry
@limits(calls=5, period=10)
@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.exceptions.RequestException,)),
    reraise=True
)
def extrair_feriados_validados(ano: int) -> dict[str, dict]:
    url = f"{BRASIL_API_URL.rstrip('/')}/feriados/v1/{ano}"
    response = requests.get(url=url, timeout=10)
    response.raise_for_status()

    dados_brutos = response.json()

    feriados_por_data = {}
    for item in dados_brutos:

        feriado = FeriadoSchema.model_validate(item)
        
        chave_data = feriado.data.isoformat()
        feriados_por_data[chave_data] = feriado.model_dump(exclude={"data"})

    return feriados_por_data


if __name__ == "__main__":
    feriados_2027 = extrair_feriados_validados(2027)
    
    print(f"Total de feriados validados: {len(feriados_2027)}")
    print("\nExemplo (2027-01-01):", feriados_2027.get("2027-01-01"))
    print(feriados_2027)