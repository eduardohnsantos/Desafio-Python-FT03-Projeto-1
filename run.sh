#!/usr/bin/env bash
set -e

echo "Iniciando pipeline de dados climáticos e feriados..."
poetry run python -m src.pipeline
echo "Pipeline executado com sucesso!"