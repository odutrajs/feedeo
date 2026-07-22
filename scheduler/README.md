# Scheduler Service

Serviço de agendamento de publicações — escrito em **Go** para consumo mínimo de recursos (~12MB de imagem Docker, ~5MB de RAM em uso).

## Arquitetura

```
┌─────────────┐     Redis Pub/Sub      ┌─────────────────┐
│  Backend    │ ──────────────────────► │  Scheduler (Go) │
│  (Python)   │                         │                 │
│             │ ◄── HTTP (execute) ──── │  Priority Queue │
└─────────────┘                         │  + Timers       │
       ▲                                └────────┬────────┘
       │                                         │
       │              WebSocket                  │
       │         ┌─────────────────┐             │
       └──────── │   Frontend      │ ◄───────────┘
                 │   (Next.js)     │   (status updates)
                 └─────────────────┘
```

### Fluxo:

1. **Frontend** → Backend: `POST /api/scheduler/schedule` (agenda publicação para horário X)
2. **Backend** → Redis Pub/Sub: notifica o scheduler do novo job
3. **Scheduler** armazena em min-heap (priority queue) e seta timer para o horário exato
4. **Quando o timer dispara**: Scheduler → Backend: `POST /api/scheduler/execute`
5. **Backend** executa a publicação (Instagram, etc.)
6. **Scheduler** → Frontend via WebSocket: notifica status em tempo real

### Por que NÃO faz polling?

- O scheduler usa uma **priority queue (min-heap)** + `time.Timer` do Go
- O timer dorme até o próximo job — zero CPU quando não há nada para fazer
- Novos agendamentos chegam via **Redis Pub/Sub** (push, não pull)
- Há um sync fallback a cada 2min como safety net (caso perca msg Redis)

## Endpoints

| Método | Path | Descrição |
|--------|------|-----------|
| POST | `/api/schedule` | Agenda um novo job |
| POST | `/api/cancel` | Cancela um job |
| GET | `/api/jobs` | Lista jobs pendentes |
| GET | `/health` | Health check |
| WS | `/ws` | WebSocket para status em tempo real |

## WebSocket

Conecte em `ws://localhost:8090/ws` para receber eventos em tempo real:

```json
{
  "publication_id": 123,
  "status": "running",
  "error": "",
  "timestamp": 1721654400
}
```

Status possíveis: `pending` → `running` → `published` / `failed`

## Variáveis de Ambiente

| Variável | Default | Descrição |
|----------|---------|-----------|
| `HTTP_ADDR` | `:8090` | Endereço do servidor HTTP |
| `REDIS_ADDR` | `localhost:6379` | Endereço do Redis |
| `REDIS_PASSWORD` | (vazio) | Senha do Redis |
| `REDIS_DB` | `0` | Database do Redis |
| `BACKEND_URL` | `http://localhost:8005` | URL do backend Python |
| `SCHEDULE_CHANNEL` | `scheduler:new` | Canal Redis para novos jobs |
| `STATUS_CHANNEL` | `scheduler:status` | Canal Redis para status |

## Rodando com Docker

```bash
# Na raiz do projeto (Creators.mov/)
docker compose up -d redis scheduler

# Verificar logs
docker compose logs scheduler -f
```

## Rodando localmente (dev)

```bash
# Precisa de Go 1.23+ e Redis rodando
cd scheduler
go run ./cmd/scheduler
```

## Deploy na Hostinger

O serviço é um container Docker independente. Para deploy em VPS Hostinger:

```bash
# Build da imagem
docker build -t creators-scheduler ./scheduler

# Ou com docker-compose
docker compose -f docker-compose.prod.yml up -d
```

A imagem final usa `scratch` (sem OS), resultando em ~12MB.
Consumo de memória em operação: ~5-10MB RAM.
