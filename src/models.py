from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Cidade(Base):
    __tablename__ = "cidades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(100), nullable=False, unique=True, index=True)
    uf = Column(String(2), nullable=True)

    medicoes = relationship("MedicaoClimatica", back_populates="cidade")


class Feriado(Base):
    __tablename__ = "feriados"

    data = Column(Date, primary_key=True)
    nome = Column(String(150), nullable=False)
    tipo = Column(String(50), nullable=False)
    dia_semana = Column(String(30), nullable=False)


class MedicaoClimatica(Base):
    __tablename__ = "medicoes_climaticas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cidade_id = Column(Integer, ForeignKey("cidades.id"), nullable=False, index=True)
    data = Column(Date, nullable=False, index=True)

    temperatura_c = Column(Float, nullable=False)
    sensacao_termica_c = Column(Float, nullable=False)
    amplitude_termica_c = Column(Float, nullable=False)
    umidade_percent = Column(Integer, nullable=False)
    descricao_clima = Column(String(150), nullable=False)
    classificacao_termica = Column(String(50), nullable=False)
    atualizado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    cidade = relationship("Cidade", back_populates="medicoes")

    __table_args__ = (
        UniqueConstraint("cidade_id", "data", name="uq_cidade_data"),
    )