# virou.ai — Vídeos virais gerados por IA

Sistema modular que transforma um tema em um vídeo vertical completo (roteiro, narração com voz personalizada, imagens geradas por IA, legendas karaokê e montagem profissional), com landing page comercial e painel de controle web.

## Três modos de criação

| Modo | Entrada | Saída |
|---|---|---|
| **Vídeo rápido** (`generative`) | Só o tema | Roteiro + imagens IA + narração + legendas |
| **Criativo** (`creative`) | Brief do produto + vídeos/fotos enviados | Anúncio curto (máx. 15s) com copy de performance (hook → problema → solução → prova → CTA) montado com os melhores trechos da mídia real |
| **Edição mágica** (`edit`) | Vídeo bruto gravado pelo criador | Corte profissional automático: remove erros, silêncios, retakes e vícios de fala, com transições e punch-ins conforme o estilo escolhido |

### Modo edição mágica

O criador grava normalmente e joga o vídeo bruto no sistema. O pipeline transcreve
tudo com timestamps por palavra (faster-whisper) e monta uma **EDL** (lista de decisões
de edição) combinando quatro detectores:

1. **Comandos de voz** — errou? Fale **"corta"** e repita a frase: a tomada ruim é
   removida para trás (incluindo o comando). Para descartar um trecho inteiro, fale
   **"corta"** no início e **"retoma"** no fim.
2. **Retakes** — frases repetidas em sequência são detectadas por similaridade fuzzy
   (rapidfuzz); só a última tomada permanece.
3. **Silêncio / ar morto** — gaps de fala acima do limiar do estilo viram jump cuts.
4. **Vícios de fala** — hesitações alongadas ("ééé", "hummm") são removidas
   (estilos dinâmico e vlog).

O usuário revisa os cortes sugeridos no painel (timeline colorida + prévia de cada
trecho, com opção de reverter qualquer decisão) e aprova; o render final usa FFmpeg em
duas passadas (extração normalizada dos trechos + concat/xfade) com loudnorm no áudio.

Estilos de edição (`config.edit_style`): `dynamic` (TikTok/Reels — jump cuts agressivos
e punch-in de zoom alternado), `vlog` (ritmo médio + crossfades em saltos grandes),
`clean` (educacional — só ar morto longo) e `podcast` (longform — limpeza mínima).

No modo criativo, cada vídeo enviado é quebrado automaticamente em trechos (detecção de corte de cena via FFmpeg), cada trecho é transcrito (Whisper) e avaliado por IA de visão (nota de qualidade, potencial de hook, tags como `product_closeup`, `talking_head`, `before_after`). O usuário pode habilitar/desabilitar trechos no painel; a IA então escreve a copy do anúncio conectada ao material disponível, escolhe o melhor trecho para cada cena (imagem IA só como fallback) e gera 3-5 hooks alternativos para teste A/B.

**Marca:** `virou.ai` — "virou" no sentido de "virou vídeo" / "viralizou". Domínio `virou.ai` disponível para registro (verificado em jul/2026).

## Projetos (workspaces) + posts estáticos e carrosséis

Um **projeto** é o espaço de trabalho da marca/campanha: guarda uma descrição rica
(produto, público-alvo, tom de voz, objetivos, ofertas, o que nunca dizer...), a
**identidade visual** (logo, cor principal/secundária, estilo visual e tema claro/escuro)
e agrupa tudo que é gerado. Esse contexto é **injetado automaticamente** nos prompts:

- **Vídeos** — ao criar um vídeo vinculado a um projeto (`workspace_id`), o roteiro
  (generative) e a copy (creative) recebem o contexto como referência obrigatória.
- **Posts estáticos e carrosséis** — gerados direto na página do projeto: a IA planeja
  headline/texto/legenda/hashtags por slide (OpenAI structured output), gera o fundo de
  cada slide com Flux (sem texto na imagem) e compõe a arte final 1080x1350 com Pillow.
  A **identidade visual** entra em duas frentes: a paleta e o estilo orientam a direção
  de arte dos fundos gerados; na composição, a logo aparece no topo, a cor principal vira
  uma barra de acento (e o número de página/hint de "deslize"), e o tema claro/escuro
  define o scrim e a cor do texto. Carrosséis seguem arco narrativo: capa-gancho →
  conteúdo → síntese → CTA.

**Rotas do frontend:**
- `/` — landing page comercial (hero, como funciona, recursos, planos de assinatura, FAQ)
- `/dashboard` — painel de criação e acompanhamento de vídeos (aceita `?workspace={id}` para vincular o vídeo a um projeto)
- `/projects/{id}` — detalhe do vídeo/pipeline
- `/workspaces` — lista e criação de projetos (nome + contexto da marca)
- `/workspaces/{id}` — página do projeto: contexto editável, vídeos e posts/carrosséis (viewer com navegação de slides, download e cópia da legenda)

## Arquitetura

```
Creators.mov/
├── backend/            # API FastAPI + pipeline (Python)
│   ├── app/
│   │   ├── api/        # Rotas REST
│   │   ├── core/       # Config, logging, exceções
│   │   ├── db/         # Models SQLAlchemy (SQLite)
│   │   ├── pipeline/   # Orquestrador + interface Stage
│   │   └── modules/    # Um módulo por etapa do pipeline
│   └── worker.py       # Worker que executa os pipelines
├── frontend/           # Painel Next.js
└── storage/
    ├── projects/{id}/  # script.json, audio/, images/, captions/, video/
    └── music/          # Trilhas sonoras (mp3) opcionais
```

Pipeline: `script → voice → audio_sync → visual_plan → images → captions → render → publish_meta`

Pipeline do modo edit: `edit_analysis → edit_render` (pausa para revisão dos cortes
após a análise, por padrão). Código em `backend/app/modules/editing/`.

No modo criativo, `script` vira a copy do anúncio (`CreativeScriptStage`) e `visual_plan` vira a seleção de trechos (`VisualSelectStage`); o `render` corta os trechos escolhidos, enquadra em 9:16 e congela o último frame quando o trecho é mais curto que a cena. As legendas sempre seguem o idioma **detectado no áudio** (Whisper auto-detect), não o configurado — evita legenda em português sobre narração em inglês.

| Módulo | Etapa | Tecnologia |
|---|---|---|
| M1 Roteiro | `script` | OpenAI structured outputs |
| M2 Narração | `voice` | ElevenLabs (voz clonada via `ELEVENLABS_VOICE_ID`) |
| M3 Sincronização | `audio_sync` | faster-whisper local (timestamps por palavra) |
| M4 Plano visual | `visual_plan` | OpenAI (style guide global + prompt por cena) |
| M5 Imagens | `images` | FLUX.2 Pro via fal.ai (qualidade premium, 1024x1536 vertical, versionadas) |
| M6 Montagem | `render` | FFmpeg (Ken Burns, xfade, loudnorm, ducking) |
| M7 Legendas | `captions` | PNGs karaokê sobrepostos (Pillow + overlay) |
| M8 Publicação | `publish_meta` | Metadados por plataforma (TikTok/Reels/Shorts) |
| M9 Upload | — | Esqueleto pronto (tabelas + interface `Publisher`) |
| M10 Painel | — | Next.js + Tailwind |

## Pré-requisitos

- Python 3.12+, Node.js 20+, FFmpeg (`brew install ffmpeg`), Docker (MinIO)
- Chaves de API: OpenAI e ElevenLabs

## Setup

```bash
# Backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # preencha OPENAI_API_KEY e ELEVENLABS_API_KEY

# Frontend
cd ../frontend
npm install
```

## Rodando

```bash
# 0. MinIO (armazenamento de vídeos — API 9010, console 9011)
docker compose up -d

# 1. API (porta 8005)
cd backend && .venv/bin/uvicorn app.main:app --reload --port 8005

# 2. Worker do pipeline
cd backend && .venv/bin/python worker.py

# 3. Painel (porta 3000)
cd frontend && npm run dev
```

### Armazenamento (MinIO)

Os vídeos enviados, thumbnails/previews dos trechos e os vídeos finais são
espelhados no MinIO (bucket `creators-media`, credenciais `creators`/`creators123`,
console em http://localhost:9011). O disco `storage/` funciona como cache de
trabalho do ffmpeg: se um arquivo não estiver no disco, o backend baixa do bucket
sob demanda, e a rota `/media` redireciona para uma URL assinada do MinIO quando o
arquivo só existe lá. Se o MinIO estiver fora do ar, tudo segue funcionando apenas
com o disco local. Configuração no `.env`: `MINIO_ENDPOINT` (vazio desativa),
`MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`.

Abra http://localhost:3000, descreva um tema e clique em "Criar vídeo".

## Configurações por projeto

O campo `config` do projeto (JSON) aceita:

| Chave | Descrição |
|---|---|
| `review_stages` | Etapas que pausam para aprovação, ex.: `["script", "images"]` |
| `style_preset` | Estilo visual desejado, ex.: `"cinematic dark fantasy"` |
| `caption_style` | Preset de legenda: `default`, `minimal`, `green_pop` |
| `voice` | `{ "voice_id", "stability", "style", "speed" }` |
| `music` | Nome de um mp3 em `storage/music/` (ducking automático) |
| `min_duration` / `max_duration` | Duração alvo do vídeo em segundos (criativo: padrão 10–15s) |
| `edit_style` | Modo edit: `dynamic`, `vlog`, `clean` ou `podcast` |
| `aspect` | Modo edit: `original` (padrão), `9:16` (TikTok/Reels/Shorts), `4:5` (feed IG), `1:1` ou `16:9` (YouTube) |
| `audio_enhance` | Modo edit: `full` (padrão — highpass, denoise, de-esser, compressão, loudnorm), `light` (highpass + loudnorm) ou `off` |
| `transition` | Modo edit: `auto` (padrão — segue o estilo), `none` (corte seco) ou um xfade (`fade`, `fadeblack`, `fadewhite`, `dissolve`, `smoothleft`, `slideleft`, `circleopen`, `radial`, `pixelize`, `hblur`, `zoomin`); aplicada nos cortes que removeram trechos grandes |

## API principal

- `POST /api/projects` — cria projeto (`mode: generative|creative`, `language`); generative dispara o pipeline
- `GET /api/projects/{id}` — detalhe com cenas, etapas, assets e mídia enviada
- `GET /api/projects/{id}/stages` — status de cada etapa (progresso)
- `POST /api/projects/{id}/run` — roda/retoma (aceita `from_stage`)
- `POST /api/projects/{id}/approve` / `reject` — revisão de etapas
- `POST /api/projects/{id}/scenes/{sid}/regenerate-image` — refaz uma imagem
- `POST /api/projects/{id}/sources` — upload de vídeos/imagens (multipart, vários arquivos); dispara análise automática
- `GET /api/projects/{id}/sources` — fontes com trechos analisados (nota, tags, transcrição)
- `PATCH /api/projects/{id}/sources/segments/{sid}` — habilita/desabilita um trecho
- `POST /api/projects/{id}/sources/{sid}/reanalyze` — refaz a análise de uma fonte
- `GET /api/projects/edit-styles` — presets de estilo do modo edit
- `GET /api/projects/edit-transitions` — transições disponíveis com prévia em vídeo de cada uma (geradas/cacheadas em `storage/transitions/`)
- `PATCH /api/projects/{id}/edit-cuts/{cid}` — inverte a decisão de um trecho (`{"action": "keep"|"cut"}`)
- `POST /api/workspaces` / `GET /api/workspaces` — cria/lista projetos (workspaces) com nome + descrição de contexto
- `GET /api/workspaces/{id}` — detalhe com vídeos vinculados e posts (com slides)
- `PATCH /api/workspaces/{id}` — edita nome/contexto/identidade visual (`brand`); `DELETE` remove (vídeos ficam, desvinculados)
- `PUT /api/workspaces/{id}/logo` (multipart) / `DELETE .../logo` — envia/remove a logo da marca
- `POST /api/workspaces/{id}/posts` — gera post (`{"kind": "static"|"carousel", "brief": "..."}`) em background
- `POST /api/workspaces/{id}/posts/{pid}/regenerate` / `DELETE .../posts/{pid}` — refaz/remove um post
- `GET /media/...` — serve os arquivos gerados

## Extensões futuras (já preparadas)

- **Publicação automática (M9)**: implemente `Publisher` em `backend/app/modules/platforms/` e registre em `PUBLISHERS`; as tabelas `platform_accounts`, `publications` e `publish_logs` já existem.
- **PostgreSQL**: troque `DATABASE_URL` no `.env` (SQLAlchemy cuida do resto).
- **Fila distribuída**: o worker consome a tabela `pipeline_jobs`; pode ser substituído por Celery sem mudar os módulos.
