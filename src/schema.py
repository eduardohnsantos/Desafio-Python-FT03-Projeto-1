from datetime import date, datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, model_validator

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


class ClimaSchema(BaseModel):
    cidade: str
    data_medicao: str
    temperatura_c: float
    sensacao_termica_c: float
    umidade_percent: int
    descricao: str

    @model_validator(mode="before")
    @classmethod
    def extrair_campos_aninhados(cls, data: dict) -> dict:
        # No endpoint /forecast, a cidade fica em 'city' e as previsões em 'list'
        city_info = data.get("city", {})
        previsoes = data.get("list", [])
        primeira_prev = previsoes[0] if previsoes else {}

        timestamp = primeira_prev.get("dt", 0)
        data_iso = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")

        main = primeira_prev.get("main", {})
        weather_list = primeira_prev.get("weather", [{}])

        return {
            "cidade": city_info.get("name"),
            "data_medicao": data_iso,
            "temperatura_c": main.get("temp"),
            "sensacao_termica_c": main.get("feels_like"),
            "umidade_percent": main.get("humidity"),
            "descricao": weather_list[0].get("description") if weather_list else "Sem descrição"
        }