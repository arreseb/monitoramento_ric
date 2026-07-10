# RICs - Servidor Web e API (Docker)

Este projeto contém um servidor Flask para monitoramento de RICs com frontend embutido e deployment em Docker.

## Estrutura principal

- `servidor_web_e_api.py` — aplicação Flask principal.
- `servidor_web_e_api_local.py` — wrapper local que inicializa o DB e roda o app.
- `start.sh` — inicializa o banco e executa `gunicorn` em produção.
- `Dockerfile` — imagem Docker para produção.
- `docker-compose.yml` — orquestração local com volume para persistência do banco.
- `requirements.txt` — dependências Python.
- `.gitignore` — arquivos a ignorar no Git.

## Executar localmente sem Docker

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python servidor_web_e_api_local.py
```

A aplicação ficará disponível em `http://localhost:5000`.

## Executar com Docker localmente

```powershell
docker build -t rics-app:prod .
docker run -d --name rics-prod -p 5000:5000 -v "$PWD\rics.db:/app/rics.db" rics-app:prod
```

## Executar com Docker Compose

```powershell
docker compose up --build -d
```

O serviço será exposto em `http://localhost:5000`.

## Preparar para GitHub

1. Crie um repositório no GitHub.
2. Inicialize o Git localmente e adicione arquivos:

```powershell
git init
git add .
git commit -m "Adicionar aplicação RICs com Docker e Gunicorn"
```

3. Conecte ao repositório remoto:

```powershell
git remote add origin https://github.com/<seu-usuario>/<seu-repo>.git
git branch -M main
git push -u origin main
```

4. Compartilhe o link do repositório com a equipe de infra.

## Nota sobre banco de dados

- O projeto usa SQLite para facilitar testes locais.
- Para produção na nuvem, a equipe de infraestrutura deve avaliar migração para um banco gerenciado (Postgres, MySQL, etc.) se precisar de alta disponibilidade ou múltiplas instâncias.

## Observações de produção

- O container utiliza `gunicorn` com 4 workers para rodar a aplicação.
- Para a nuvem, prefira serviços de container como AWS ECS/Fargate ou Elastic Beanstalk.
- Se precisar manter persistência de dados em SQLite, monte o volume `./rics.db:/app/rics.db`.
