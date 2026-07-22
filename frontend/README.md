# Creators.mov — Frontend

Painel Next.js + landing page do Creators.mov / virou.ai.

## Setup

```bash
npm install
npm run dev
```

App em http://localhost:3000

Rotas:
- `/` — landing
- `/workspaces` — lista de projetos
- `/workspaces/{id}` — detalhe do projeto (vídeos, posts, calendário)
- `/dashboard?workspace={id}` — criação de vídeo (requer workspace)
- `/projects/{id}` — detalhe do vídeo
