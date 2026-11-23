# 🌦️ Pipeline de Engenharia de Dados: Inteligência Climática & Feriados para Turismo

## 🎯 Contexto de Negócio e Objetivo

Empresas do setor de **turismo, hotelaria e logística de viagens** enfrentam alta sazonalidade e precisam antecipar a demanda e os riscos operacionais nas principais capitais do Brasil durante os feriados nacionais.

Este projeto implementa um **produto de dados ponta a ponta (End-to-End)** criado para apoiar equipes de planejamento turístico e precificação dinâmica. O pipeline cruza automaticamente as **previsões meteorológicas de 5 dias** das 27 capitais brasileiras com o **calendário oficial de feriados nacionais**, entregando indicadores prontos para consumo analítico — como **classificação térmica**, **amplitude térmica** e **índice de desconforto térmico** — tanto em **Data Lake (Parquet particionado)** quanto em **Data Warehouse relacional (PostgreSQL)**.

---

## 🏗️ Arquitetura e Fluxo de Dados

O pipeline segue uma arquitetura em camadas com processamento analítico via **DuckDB**, validação rigorosa de **Data Quality** e carga idempotente (Upsert) em **PostgreSQL (Render)**:

```text
┌─────────────────────────┐      ┌─────────────────────────┐
│    OpenWeather API      │      │       BrasilAPI         │
│ (Forecast - 27 Capitais)│      │  (Feriados Nacionais)   │
└────────────┬────────────┘      └────────────┬────────────┘
             │ HTTP GET (Retries/Rate Limit)  │
             ▼                                ▼
┌──────────────────────────────────────────────────────────┐
│                  Camada Raw (data/raw/)                  │
│          JSONs Brutos Validados (Pydantic)               │
└────────────────────────────┬─────────────────────────────┘
                             │ SQL / DuckDB + Pandas
                             ▼
┌──────────────────────────────────────────────────────────┐
│            Camada Gold & Governança (output/)            │
│  • Enriquecimento (Clima + Feriados + Indicadores)       │
│  • Dataset Particionado por ano/mes (.parquet)           │
│  • Relatório de Data Quality (data_quality_report.json)  │
└────────────────────────────┬─────────────────────────────┘
                             │ SQLAlchemy ORM (Upsert)
                             ▼
┌──────────────────────────────────────────────────────────┐
│          Camada Serving: PostgreSQL (Render)             │
│  Modelo Relacional: cidades | feriados | medicoes_clima  │
└──────────────────────────────────────────────────────────┘
```

---

## 📂 Estrutura do Repositório

```text
├── data/
│   └── raw/                     # Dados brutos ingeridos das APIs (JSON)
├── output/                      # Entregáveis persistidos
│   ├── clima_feriados/          # Dataset final limpo e particionado (ano/mes/*.parquet)
│   └── data_quality_report.json # Métricas e auditoria de qualidade de dados
├── src/                         # Código-fonte modular
│   ├── extract.py               # Extração HTTP com tratamento de exceções e retries
│   ├── transform.py             # Transformações analíticas em SQL com DuckDB
│   ├── quality.py               # Validações de schema, nulos, domínio e duplicidade
│   ├── models.py                # Definição ORM das tabelas relacionais (SQLAlchemy)
│   ├── load_db.py               # Carga idempotente (Upsert) no PostgreSQL
│   └── pipeline.py              # Orquestrador principal do fluxo ponta a ponta
├── .env.example                 # Modelo das variáveis de ambiente necessárias
├── .gitignore                   # Arquivos ignorados pelo controle de versão
├── pyproject.toml               # Configuração do projeto e dependências (Poetry)
├── requirements.txt             # Lista exata de bibliotecas para reprodução
├── run.sh                       # Script executável ponta a ponta
└── README.md                    # Documentação do projeto
```

---

## 🌐 Documentação das APIs Consumidas

### 1. OpenWeatherMap API (5 Day / 3 Hour Forecast)
* **Finalidade:** Coleta das previsões meteorológicas (temperatura, sensação térmica, mínima, máxima, umidade e descrição do tempo) para as 27 capitais brasileiras.
* **Endpoint:** `https://api.openweathermap.org/data/2.5/forecast`
* **Parâmetros:** `q={cidade},{uf},BR`, `appid={OPENWEATHER_API_KEY}`, `units=metric`, `lang=pt_br`.
* **Resiliência:** Implementação de *retries* com *exponential backoff* em falhas temporárias (`429`/`5xx`), controle de *timeout* e cadência entre requisições.

### 2. BrasilAPI (Feriados Nacionais)
* **Finalidade:** Obtenção do calendário oficial de feriados nacionais para enriquecimento temporal das medições climáticas.
* **Endpoint:** `https://brasilapi.com.br/api/feriados/v1/{ano}`
* **Autenticação:** Pública (não requer chave de API).

---

## 🗄️ Modelagem de Dados (PostgreSQL)

Na camada Serving (PostgreSQL hospedado no Render), os dados são normalizados em **3 tabelas** para garantir integridade referencial e permitir consultas analíticas eficientes:

1. **`cidades` (Dimensão):**
   * `id` (PK, Integer, Auto-increment)
   * `nome` (String, Unique, Not Null) — Ex: `"São Paulo"`
   * `uf` (String(2), Not Null) — Ex: `"SP"`
2. **`feriados` (Dimensão):**
   * `data` (PK, Date) — Ex: `2026-11-15`
   * `nome` (String, Not Null) — Ex: `"Proclamação da República"`
   * `tipo` (String) — Ex: `"national"`
   * `dia_semana` (String) — Ex: `"Domingo"`
3. **`medicoes_climaticas` (Fato):**
   * `id` (PK, Integer, Auto-increment)
   * `cidade_id` (FK -> `cidades.id`, Not Null)
   * `data` (Date, Not Null) — *Constraint `uq_cidade_data` para garantir idempotência via Upsert*
   * `temperatura_c` (Float)
   * `sensacao_termica_c` (Float)
   * `amplitude_termica_c` (Float)
   * `umidade_percent` (Integer)
   * `descricao_clima` (String)
   * `classificacao_termica` (String) — Ex: `"Calor Intenso"`, `"Agradável"`, `"Frio / Ameno"`

---

## 🛡️ Governança e Data Quality

Antes da persistência final, o pipeline executa uma auditoria automatizada (`src/quality.py`) que bloqueia a gravação caso alguma regra falhe:
* **Completude e Schema:** Verificação das 10 colunas obrigatórias e cálculo da taxa de nulos (`null_ratio_por_coluna`).
* **Unicidade:** Garantia de zero duplicatas na chave composta `(cidade, data)`.
* **Validade de Domínio:** Faixas físicas coerentes para temperatura (`-50°C` a `60°C`) e umidade relativa (`0%` a `100%`).

Os resultados são exportados automaticamente em `output/data_quality_report.json`.

---

## ⚙️ Configuração e Variáveis de Ambiente

1. Clone o repositório:
   ```bash
   git clone https://github.com/eduardohnsantos/Desafio-Python-FT03-Projeto-1
   cd Desafio-Python-FT03-Projeto-1
   ```

2. Crie um arquivo `.env` na raiz do projeto baseado no `.env.example`:
   ```env
   OPENWEATHER_API_KEY=sua_chave_da_openweather
   DATABASE_URL=postgresql+psycopg2://usuario:senha@host:5432/db_clima_feriados?sslmode=require
   ```

---

## 🚀 Como Executar o Pipeline

### Opção 1: Via Script Executável (`run.sh`)
```bash
chmod +x run.sh
./run.sh
```

### Opção 2: Via Poetry (Recomendado)
```bash
poetry install
poetry run python -m src.pipeline
```

### Opção 3: Via `pip` padrão (`requirements.txt`)
```bash
python -m venv .venv
source .venv/bin/activate  # No Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m src.pipeline
```

---

## 🔍 Exemplo de Consulta Analítica (PostgreSQL)

```sql
SELECT 
    c.uf,
    c.nome AS cidade,
    m.data,
    m.temperatura_c,
    m.sensacao_termica_c,
    m.classificacao_termica,
    COALESCE(f.nome, 'Dia comum') AS status_feriado,
    COALESCE(
        f.dia_semana,
        CASE EXTRACT(DOW FROM m.data)
            WHEN 0 THEN 'Domingo'
            WHEN 1 THEN 'Segunda-feira'
            WHEN 2 THEN 'Terça-feira'
            WHEN 3 THEN 'Quarta-feira'
            WHEN 4 THEN 'Quinta-feira'
            WHEN 5 THEN 'Sexta-feira'
            WHEN 6 THEN 'Sábado'
        END
    ) AS dia_semana
FROM medicoes_climaticas m
JOIN cidades c ON m.cidade_id = c.id
LEFT JOIN feriados f ON m.data = f.data
ORDER BY m.temperatura_c DESC;
```