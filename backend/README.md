# Creators.mov — Backend

API FastAPI + pipeline de geração de vídeos (Python).

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # preencha as chaves de API
```

## Rodando

```bash
# MinIO (opcional — storage de mídia)
docker compose up -d

# API
.venv/bin/uvicorn app.main:app --reload --port 8000

# Worker (outro terminal)
.venv/bin/python worker.py
```

Docs interativas: http://localhost:8000/docs
