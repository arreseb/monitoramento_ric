#!/bin/sh
set -e

# Inicializa o banco (cria tabela se necessário)
python - <<'PY'
from servidor_web_e_api import inicializar_banco
inicializar_banco()
print('Banco inicializado')
PY

# Executa o Gunicorn com 4 workers
exec gunicorn -w 4 -b 0.0.0.0:5000 servidor_web_e_api:app
