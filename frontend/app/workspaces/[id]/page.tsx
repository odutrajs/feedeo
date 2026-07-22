"use client";

import { use, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, BrandIdentity, mediaUrl, Project, SocialPost, WorkspaceDetail, instagramConnectUrl, formatScheduledAt, localDateTimeToISO, toLocalDateValue, toLocalTimeValue, shouldPollPublications } from "@/lib/api";

// ── Constants ────────────────────────────────────────────────────────

const STATUS_LABEL: Record<string, { label: string; className: string }> = {
  draft: { label: "Rascunho", className: "bg-white/[0.06] text-white/50" },
  queued: { label: "Na fila", className: "bg-[--cyan-soft] text-[#64d2ff]" },
  running: { label: "Processando", className: "bg-[--orange-soft] text-[#ff9f0a]" },
  awaiting_review: { label: "Aguardando revisão", className: "bg-[--purple-soft] text-[#bf5af2]" },
  completed: { label: "Concluído", className: "bg-[--green-soft] text-[#30d158]" },
  failed: { label: "Falhou", className: "bg-[--red-soft] text-[#ff453a]" },
};

const MODE_TAGS: Record<string, string> = {
  generative: "Vídeo rápido",
  creative: "Criativo",
  edit: "Edição",
};

type TabId = "videos" | "posts" | "calendar" | "settings";

const TABS: { id: TabId; label: string; short: string; icon: React.ReactNode }[] = [
  {
    id: "videos",
    label: "Vídeos",
    short: "Vídeos",
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <polygon points="23 7 16 12 23 17 23 7" />
        <rect x="1" y="5" width="15" height="14" rx="2" />
      </svg>
    ),
  },
  {
    id: "posts",
    label: "Posts & Carrosséis",
    short: "Posts",
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="18" height="18" rx="3" />
        <circle cx="8.5" cy="8.5" r="1.5" />
        <path d="m21 15-5-5L5 21" />
      </svg>
    ),
  },
  {
    id: "calendar",
    label: "Calendário",
    short: "Agenda",
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="4" width="18" height="18" rx="2" />
        <line x1="16" y1="2" x2="16" y2="6" />
        <line x1="8" y1="2" x2="8" y2="6" />
        <line x1="3" y1="10" x2="21" y2="10" />
      </svg>
    ),
  },
  {
    id: "settings",
    label: "Configurações",
    short: "Config",
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="3" />
        <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
      </svg>
    ),
  },
];

function Badge({ status }: { status: string }) {
  const cfg = STATUS_LABEL[status] ?? { label: status, className: "bg-white/[0.06] text-white/50" };
  return (
    <span className={`inline-flex shrink-0 items-center rounded-full px-2.5 py-1 text-[10px] font-medium sm:text-[11px] ${cfg.className}`}>
      {cfg.label}
    </span>
  );
}

// ── Post Card ────────────────────────────────────────────────────────

function PostCard({
  post,
  workspaceId,
  igConnected,
}: {
  post: SocialPost;
  workspaceId: number;
  igConnected: boolean;
}) {
  const queryClient = useQueryClient();
  const [slide, setSlide] = useState(0);
  const [copied, setCopied] = useState(false);
  const [showSchedule, setShowSchedule] = useState(false);
  const [scheduleDay, setScheduleDay] = useState(() => toLocalDateValue(new Date()));
  const [scheduleTime, setScheduleTime] = useState(() => {
    const d = new Date();
    d.setMinutes(d.getMinutes() + 30);
    return toLocalTimeValue(d);
  });

  const regenerate = useMutation({
    mutationFn: () => api.regenerateSocialPost(workspaceId, post.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspace", workspaceId] }),
  });
  const remove = useMutation({
    mutationFn: () => api.deleteSocialPost(workspaceId, post.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspace", workspaceId] }),
  });

  const { data: publications } = useQuery({
    queryKey: ["publications", "post", post.id],
    queryFn: () => api.listPublications({ socialPostId: post.id }),
    enabled: post.status === "completed",
    refetchInterval: (query) => shouldPollPublications(query.state.data),
  });

  const publish = useMutation({
    mutationFn: () => api.publishPostToInstagram(post.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["publications", "post", post.id] }),
  });

  const schedule = useMutation({
    mutationFn: (scheduledAt: string) => api.schedulePost({ socialPostId: post.id, scheduledAt }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["publications", "post", post.id] });
      setShowSchedule(false);
    },
  });

  const cancelSchedule = useMutation({
    mutationFn: (publicationId: number) => api.cancelSchedule(publicationId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["publications", "post", post.id] }),
  });

  const slides = post.slides;
  const current = slides[Math.min(slide, Math.max(slides.length - 1, 0))];
  const isWorking = post.status === "queued" || post.status === "running";
  const latestPub = publications?.[0];
  const isPublished = publications?.some((p) => p.status === "published") ?? false;
  const isPublishing = publish.isPending || latestPub?.status === "uploading";
  const scheduledPub = publications?.find((p) => p.status === "scheduled" && p.scheduled_at);
  const canPublish =
    igConnected &&
    post.status === "completed" &&
    slides.some((s) => s.composed_path || s.image_path) &&
    !isPublished &&
    !isPublishing;

  function copyCaption() {
    const tags = (post.hashtags ?? []).map((h) => `#${h}`).join(" ");
    navigator.clipboard.writeText([post.caption, tags].filter(Boolean).join("\n\n"));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="glass overflow-hidden rounded-2xl">
      <div className="relative aspect-[4/5] w-full bg-black/40">
        {current?.composed_path ? (
          <img src={mediaUrl(current.composed_path)} alt={current.headline} className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full w-full flex-col items-center justify-center gap-2 text-white/25">
            {isWorking ? (
              <>
                <svg className="h-6 w-6 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" className="opacity-25" />
                  <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
                </svg>
                <span className="text-[11px]">{post.status === "queued" ? "Na fila..." : "Gerando arte..."}</span>
              </>
            ) : post.status === "failed" ? (
              <span className="max-w-[80%] text-center text-[11px] text-[#ff453a]">{post.error ?? "Falhou"}</span>
            ) : (
              <span className="text-[11px]">Sem imagem</span>
            )}
          </div>
        )}

        {slides.length > 1 && (
          <>
            {slide > 0 && (
              <button onClick={() => setSlide((s) => s - 1)} className="absolute left-2 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full bg-black/60 text-white/80 backdrop-blur transition-colors hover:bg-black/80">‹</button>
            )}
            {slide < slides.length - 1 && (
              <button onClick={() => setSlide((s) => s + 1)} className="absolute right-2 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full bg-black/60 text-white/80 backdrop-blur transition-colors hover:bg-black/80">›</button>
            )}
            <div className="absolute bottom-2 left-1/2 flex -translate-x-1/2 gap-1.5">
              {slides.map((s, i) => (
                <button key={s.id} onClick={() => setSlide(i)} className={`h-1.5 rounded-full transition-all ${i === slide ? "w-4 bg-white" : "w-1.5 bg-white/40"}`} />
              ))}
            </div>
          </>
        )}

        <span className="absolute left-2 top-2 rounded-full bg-black/60 px-2.5 py-1 text-[10px] font-semibold text-white/80 backdrop-blur">
          {post.kind === "carousel" ? `Carrossel · ${slides.length || "?"} slides` : "Post estático"}
        </span>
      </div>

      <div className="space-y-2.5 p-4">
        <p className="line-clamp-1 text-[12px] font-medium text-white/60">{post.brief}</p>
        {post.caption && (
          <p className="line-clamp-3 whitespace-pre-line text-[11px] leading-relaxed text-white/35">{post.caption}</p>
        )}

        {latestPub && latestPub.status !== "scheduled" && (
          <div className="flex items-center gap-2 rounded-lg bg-white/[0.03] px-2.5 py-1.5">
            <span className={`h-1.5 w-1.5 rounded-full ${latestPub.status === "published" ? "bg-green-400" : latestPub.status === "failed" ? "bg-red-400" : "bg-yellow-400 animate-pulse"}`} />
            <span className="text-[11px] text-white/50">
              {latestPub.status === "published" ? "Publicado no Instagram" : latestPub.status === "failed" ? latestPub.error ?? "Falha ao publicar" : "Publicando..."}
            </span>
            {latestPub.status === "published" && latestPub.external_id && (
              <a href={`https://www.instagram.com/p/${latestPub.external_id}/`} target="_blank" rel="noopener noreferrer" className="ml-auto text-[10px] text-[#c084fc] hover:underline">Ver →</a>
            )}
          </div>
        )}

        {scheduledPub && !isPublished && (
          <div className="flex items-start gap-2 rounded-lg border border-[#a855f7]/20 bg-[#a855f7]/[0.08] px-2.5 py-2">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mt-0.5 shrink-0 text-[#c084fc]">
              <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
            </svg>
            <span className="min-w-0 flex-1 text-[11px] leading-snug text-[#c084fc]">
              Agendado para {formatScheduledAt(scheduledPub.scheduled_at!)}
            </span>
            <button
              onClick={() => cancelSchedule.mutate(scheduledPub.id)}
              disabled={cancelSchedule.isPending}
              className="shrink-0 text-[10px] text-white/30 transition-colors hover:text-[#ff453a] disabled:opacity-50"
            >
              Cancelar
            </button>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2 pt-1">
          {canPublish && !scheduledPub && (
            <>
              <button onClick={() => publish.mutate()} className="rounded-lg bg-gradient-to-r from-[#f58529] via-[#dd2a7b] to-[#8134af] px-2.5 py-1.5 text-[11px] font-semibold text-white transition hover:opacity-90">
                Postar no Instagram
              </button>
              <button
                onClick={() => setShowSchedule((v) => !v)}
                className="rounded-lg border border-[#a855f7]/30 bg-[#a855f7]/[0.08] px-2.5 py-1.5 text-[11px] font-medium text-[#c084fc] transition-colors hover:bg-[#a855f7]/[0.15]"
              >
                <span className="flex items-center gap-1.5">
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
                  </svg>
                  Agendar
                </span>
              </button>
            </>
          )}
          {post.caption && (
            <button onClick={copyCaption} className="rounded-lg bg-white/[0.06] px-2.5 py-1.5 text-[11px] font-medium text-white/60 transition-colors hover:bg-white/[0.1] hover:text-white/90">
              {copied ? "Copiado!" : "Copiar legenda"}
            </button>
          )}
          {current?.composed_path && (
            <a href={mediaUrl(current.composed_path)} download target="_blank" rel="noreferrer" className="rounded-lg bg-white/[0.06] px-2.5 py-1.5 text-[11px] font-medium text-white/60 transition-colors hover:bg-white/[0.1] hover:text-white/90">
              Baixar {slides.length > 1 ? `slide ${slide + 1}` : "imagem"}
            </a>
          )}
          <div className="ml-auto flex items-center gap-1">
            {!isWorking && (
              <button onClick={() => regenerate.mutate()} className="rounded-lg px-2 py-1.5 text-[11px] text-white/30 transition-colors hover:text-[#c084fc]">Regenerar</button>
            )}
            <button onClick={() => { if (confirm("Excluir este post?")) remove.mutate(); }} className="rounded-lg px-2 py-1.5 text-[11px] text-white/30 transition-colors hover:text-[#ff453a]">Excluir</button>
          </div>
        </div>

        {showSchedule && canPublish && !scheduledPub && (
          <div className="mt-2 space-y-2.5 rounded-xl border border-white/[0.06] bg-black/30 p-3">
            <p className="text-[11px] font-medium text-white/50">Agendar publicação</p>
            <div className="grid grid-cols-2 gap-2">
              <label className="block space-y-1">
                <span className="text-[10px] text-white/35">Data</span>
                <input
                  type="date"
                  value={scheduleDay}
                  min={toLocalDateValue(new Date())}
                  onChange={(e) => setScheduleDay(e.target.value)}
                  className="w-full rounded-lg border border-white/[0.08] bg-white/[0.04] px-2.5 py-2 text-[12px] text-white/80 outline-none focus:border-[#a855f7]/50 [color-scheme:dark]"
                />
              </label>
              <label className="block space-y-1">
                <span className="text-[10px] text-white/35">Hora</span>
                <input
                  type="time"
                  value={scheduleTime}
                  onChange={(e) => setScheduleTime(e.target.value)}
                  className="w-full rounded-lg border border-white/[0.08] bg-white/[0.04] px-2.5 py-2 text-[12px] text-white/80 outline-none focus:border-[#a855f7]/50 [color-scheme:dark]"
                />
              </label>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setShowSchedule(false)}
                className="flex-1 rounded-lg bg-white/[0.06] px-3 py-2 text-[11px] font-medium text-white/50 transition hover:bg-white/[0.1] hover:text-white/80"
              >
                Fechar
              </button>
              <button
                type="button"
                onClick={() => {
                  if (!scheduleDay || !scheduleTime) return;
                  const iso = localDateTimeToISO(scheduleDay, scheduleTime);
                  if (new Date(iso).getTime() <= Date.now()) {
                    alert("Escolha um horário no futuro");
                    return;
                  }
                  schedule.mutate(iso);
                }}
                disabled={!scheduleDay || !scheduleTime || schedule.isPending}
                className="flex-1 rounded-lg bg-[#a855f7] px-3 py-2 text-[11px] font-semibold text-white transition hover:bg-[#9333ea] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {schedule.isPending ? "Agendando..." : "Confirmar"}
              </button>
            </div>
            {schedule.isError && (
              <p className="text-[10px] text-red-400">{(schedule.error as Error)?.message ?? "Erro ao agendar"}</p>
            )}
          </div>
        )}

        {publish.isError && (
          <p className="text-[11px] text-red-400">{(publish.error as Error)?.message ?? "Falha ao publicar"}</p>
        )}
      </div>
    </div>
  );
}

// ── Tab: Vídeos ──────────────────────────────────────────────────────

function VideosTab({ workspace }: { workspace: WorkspaceDetail }) {
  return (
    <div className="space-y-3 animate-slide-up">
      <div className="flex items-center justify-between">
        <p className="text-[13px] text-white/40">
          {workspace.projects.length === 0
            ? "Nenhum vídeo neste projeto ainda. Crie o primeiro!"
            : `${workspace.projects.length} vídeo${workspace.projects.length === 1 ? "" : "s"}`}
        </p>
        <Link
          href={`/dashboard?workspace=${workspace.id}`}
          className="btn-gradient rounded-xl px-4 py-2 text-[12px] font-semibold text-white shadow-lg shadow-[#a855f7]/20"
        >
          + Novo vídeo
        </Link>
      </div>

      {workspace.projects.length === 0 ? (
        <div className="glass flex flex-col items-center justify-center rounded-2xl py-14 text-center">
          <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-white/[0.04]">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-white/20">
              <polygon points="23 7 16 12 23 17 23 7" /><rect x="1" y="5" width="15" height="14" rx="2" />
            </svg>
          </div>
          <p className="text-[13px] text-white/30">Crie um vídeo e a IA usará o contexto deste projeto.</p>
          <Link
            href={`/dashboard?workspace=${workspace.id}`}
            className="btn-gradient mt-4 rounded-xl px-5 py-2.5 text-[13px] font-semibold text-white shadow-lg shadow-[#a855f7]/20"
          >
            Criar primeiro vídeo
          </Link>
        </div>
      ) : (
        <div className="space-y-2">
          {workspace.projects.map((project: Project) => (
            <Link
              key={project.id}
              href={`/projects/${project.id}`}
              className="glass glass-hover group flex items-center justify-between gap-3 rounded-xl px-3.5 py-3.5 transition-all sm:rounded-2xl sm:px-5 sm:py-4"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-[14px] font-medium tracking-tight text-white/90 group-hover:text-white sm:text-[15px]">
                  {project.title ?? project.topic}
                </p>
                <p className="mt-0.5 truncate text-[11px] text-white/25 sm:text-[12px]">
                  #{project.id} · {MODE_TAGS[project.mode] ?? project.mode} ·{" "}
                  {new Date(project.created_at).toLocaleString("pt-BR")}
                </p>
              </div>
              <Badge status={project.status} />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Tab: Posts & Carrosséis ──────────────────────────────────────────

function PostsTab({ workspace, igConnected }: { workspace: WorkspaceDetail; igConnected: boolean }) {
  const queryClient = useQueryClient();
  const [postKind, setPostKind] = useState<"static" | "carousel">("carousel");
  const [postBrief, setPostBrief] = useState("");

  const createPost = useMutation({
    mutationFn: () => api.createSocialPost(workspace.id, { kind: postKind, brief: postBrief.trim() }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workspace", workspace.id] });
      setPostBrief("");
    },
  });

  return (
    <div className="space-y-4 animate-slide-up">
      {/* Criar post */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (postBrief.trim().length >= 3) createPost.mutate();
        }}
        className="glass space-y-3 rounded-2xl p-4 sm:p-5"
      >
        <div className="flex gap-1.5 rounded-xl bg-white/[0.04] p-1 sm:w-fit">
          {([
            { id: "carousel", label: "Carrossel", hint: "6-8 slides" },
            { id: "static", label: "Post estático", hint: "1 imagem" },
          ] as const).map((k) => (
            <button
              key={k.id}
              type="button"
              onClick={() => setPostKind(k.id)}
              className={`flex-1 rounded-lg px-4 py-2 text-[12px] font-semibold transition-all sm:flex-none ${
                postKind === k.id
                  ? "bg-gradient-to-br from-[#a855f7] to-[#ec4899] text-white shadow-lg shadow-[#a855f7]/20"
                  : "text-white/40 hover:text-white/70"
              }`}
            >
              {k.label}
              <span className={`ml-1.5 hidden text-[10px] font-normal sm:inline ${postKind === k.id ? "text-white/70" : "text-white/25"}`}>
                {k.hint}
              </span>
            </button>
          ))}
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            value={postBrief}
            onChange={(e) => setPostBrief(e.target.value)}
            placeholder={
              postKind === "carousel"
                ? "Tema do carrossel — ex.: 5 erros que afastam clientes do seu perfil"
                : "Tema do post — ex.: frase de impacto sobre nosso diferencial"
            }
            className="flex-1 rounded-xl border border-white/[0.06] bg-white/[0.03] px-3.5 py-3 text-[13px] text-white/90 placeholder:text-white/20 transition-all focus:border-[#a855f7]/40 focus:bg-white/[0.05]"
          />
          <button
            type="submit"
            disabled={createPost.isPending || postBrief.trim().length < 3}
            className="btn-gradient shrink-0 rounded-xl px-5 py-3 text-[13px] font-semibold text-white shadow-lg shadow-[#a855f7]/20 disabled:opacity-30 disabled:shadow-none"
          >
            {createPost.isPending ? "Criando..." : "Gerar com IA"}
          </button>
        </div>
        <p className="text-[11px] text-white/25">
          A IA escreve o texto e a legenda usando o contexto do projeto, e gera as artes prontas para publicar.
        </p>
      </form>

      {workspace.posts.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {workspace.posts.map((post) => (
            <PostCard key={post.id} post={post} workspaceId={workspace.id} igConnected={igConnected} />
          ))}
        </div>
      ) : (
        <div className="glass flex flex-col items-center justify-center rounded-2xl py-14 text-center">
          <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-white/[0.04]">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-white/20">
              <rect x="3" y="3" width="18" height="18" rx="4" /><circle cx="8.5" cy="8.5" r="1.5" /><path d="m21 15-5-5L5 21" />
            </svg>
          </div>
          <p className="text-[13px] text-white/30">Nenhum post ainda.</p>
          <p className="mt-1 text-[11px] text-white/20">Gere posts estáticos e carrosséis com IA acima.</p>
        </div>
      )}
    </div>
  );
}

// ── Tab: Calendário ──────────────────────────────────────────────────

function CalendarTab({ workspaceId }: { workspaceId: number }) {
  const [currentMonth, setCurrentMonth] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });

  const { data: publications } = useQuery({
    queryKey: ["calendar_publications", workspaceId, currentMonth.toISOString()],
    queryFn: () => api.listPublications({ workspaceId }),
    staleTime: 30_000,
  });

  const scheduled = (publications ?? []).filter(
    (p) => p.status === "scheduled" || p.status === "published"
  );

  const year = currentMonth.getFullYear();
  const month = currentMonth.getMonth();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const firstDayOfWeek = new Date(year, month, 1).getDay(); // 0=Sun

  const prevMonth = () => setCurrentMonth(new Date(year, month - 1, 1));
  const nextMonth = () => setCurrentMonth(new Date(year, month + 1, 1));

  const today = new Date();
  const isToday = (day: number) =>
    today.getFullYear() === year && today.getMonth() === month && today.getDate() === day;

  const getEventsForDay = (day: number) => {
    return scheduled.filter((pub) => {
      if (!pub.scheduled_at) return false;
      const d = new Date(pub.scheduled_at);
      return d.getFullYear() === year && d.getMonth() === month && d.getDate() === day;
    });
  };

  const WEEKDAYS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];
  const MONTH_NAMES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
  ];

  const cells: (number | null)[] = [];
  for (let i = 0; i < firstDayOfWeek; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);

  const [selectedDay, setSelectedDay] = useState<number | null>(null);
  const selectedEvents = selectedDay ? getEventsForDay(selectedDay) : [];

  return (
    <div className="glass rounded-2xl p-5 sm:rounded-3xl sm:p-6 space-y-4">
      {/* Header do mês */}
      <div className="flex items-center justify-between">
        <button onClick={prevMonth} className="rounded-lg px-3 py-1.5 text-white/40 transition-colors hover:bg-white/[0.06] hover:text-white/80">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>
        <h2 className="text-[14px] font-semibold text-white/80 sm:text-[16px]">
          {MONTH_NAMES[month]} {year}
        </h2>
        <button onClick={nextMonth} className="rounded-lg px-3 py-1.5 text-white/40 transition-colors hover:bg-white/[0.06] hover:text-white/80">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </button>
      </div>

      {/* Weekday headers */}
      <div className="grid grid-cols-7 gap-1">
        {WEEKDAYS.map((wd) => (
          <div key={wd} className="py-2 text-center text-[10px] font-medium uppercase tracking-wider text-white/30">
            {wd}
          </div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className="grid grid-cols-7 gap-1">
        {cells.map((day, i) => {
          if (day === null) {
            return <div key={`empty-${i}`} className="aspect-square" />;
          }
          const events = getEventsForDay(day);
          const hasScheduled = events.some((e) => e.status === "scheduled");
          const hasPublished = events.some((e) => e.status === "published");
          const isSelected = selectedDay === day;

          return (
            <button
              key={day}
              onClick={() => setSelectedDay(day === selectedDay ? null : day)}
              className={`relative flex aspect-square flex-col items-center justify-center rounded-lg transition-all text-[12px] sm:text-[13px] font-medium ${
                isSelected
                  ? "bg-[#a855f7]/20 ring-1 ring-[#a855f7]/50 text-white"
                  : isToday(day)
                  ? "bg-white/[0.08] text-white ring-1 ring-white/20"
                  : "text-white/60 hover:bg-white/[0.04] hover:text-white/80"
              }`}
            >
              <span>{day}</span>
              {(hasScheduled || hasPublished) && (
                <div className="absolute bottom-1 flex gap-0.5">
                  {hasScheduled && <span className="h-1.5 w-1.5 rounded-full bg-[#a855f7]" />}
                  {hasPublished && <span className="h-1.5 w-1.5 rounded-full bg-[#30d158]" />}
                </div>
              )}
            </button>
          );
        })}
      </div>

      {/* Legenda */}
      <div className="flex items-center gap-4 pt-2 text-[11px] text-white/40">
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-[#a855f7]" /> Agendado
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-[#30d158]" /> Publicado
        </span>
      </div>

      {/* Detalhes do dia selecionado */}
      {selectedDay && (
        <div className="space-y-2 border-t border-white/[0.06] pt-4">
          <h3 className="text-[12px] font-semibold text-white/60">
            {selectedDay} de {MONTH_NAMES[month]}
          </h3>
          {selectedEvents.length === 0 ? (
            <p className="text-[12px] text-white/30">Nenhuma publicação neste dia.</p>
          ) : (
            <div className="space-y-2">
              {selectedEvents.map((pub) => {
                const time = pub.scheduled_at
                  ? new Date(pub.scheduled_at).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })
                  : "--:--";
                return (
                  <div
                    key={pub.id}
                    className="flex items-center gap-3 rounded-xl bg-white/[0.03] px-4 py-3"
                  >
                    <span
                      className={`h-2 w-2 shrink-0 rounded-full ${
                        pub.status === "published" ? "bg-[#30d158]" : "bg-[#a855f7]"
                      }`}
                    />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[12px] font-medium text-white/80">
                        {pub.status === "published" ? "Publicado" : "Agendado"} — Post #{pub.social_post_id || pub.project_id}
                      </p>
                    </div>
                    <span className="shrink-0 text-[11px] font-medium text-white/40">{time}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Tab: Configurações ───────────────────────────────────────────────

const SWATCHES = ["#a855f7", "#ec4899", "#12b76a", "#0ea5e9", "#f59e0b", "#ef4444", "#111827", "#f8fafc"];

function SettingsTab({ workspace }: { workspace: WorkspaceDetail }) {
  const queryClient = useQueryClient();
  const logoInputRef = useRef<HTMLInputElement>(null);

  const [editingContext, setEditingContext] = useState(false);
  const [draftDescription, setDraftDescription] = useState("");
  const [brand, setBrand] = useState<BrandIdentity>({
    primary_color: workspace.brand?.primary_color ?? "",
    secondary_color: workspace.brand?.secondary_color ?? "",
    visual_style: workspace.brand?.visual_style ?? "",
    text_theme: workspace.brand?.text_theme ?? "dark",
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["workspace", workspace.id] });

  const saveContext = useMutation({
    mutationFn: () => api.updateWorkspace(workspace.id, { description: draftDescription }),
    onSuccess: () => { invalidate(); setEditingContext(false); },
  });
  const saveBrand = useMutation({
    mutationFn: () => api.updateWorkspace(workspace.id, { brand }),
    onSuccess: invalidate,
  });
  const uploadLogo = useMutation({
    mutationFn: (file: File) => api.uploadWorkspaceLogo(workspace.id, file),
    onSuccess: invalidate,
  });
  const removeLogo = useMutation({
    mutationFn: () => api.deleteWorkspaceLogo(workspace.id),
    onSuccess: invalidate,
  });

  const disconnect = useMutation({
    mutationFn: () => api.disconnectInstagram(workspace.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["instagram_status", workspace.id] }),
  });

  const { data: igStatus } = useQuery({
    queryKey: ["instagram_status", workspace.id],
    queryFn: () => api.getInstagramStatus(workspace.id),
    staleTime: 30_000,
  });

  const brandDirty =
    brand.primary_color !== (workspace.brand?.primary_color ?? "") ||
    brand.secondary_color !== (workspace.brand?.secondary_color ?? "") ||
    brand.visual_style !== (workspace.brand?.visual_style ?? "") ||
    brand.text_theme !== (workspace.brand?.text_theme ?? "dark");

  function ColorField({ label, keyName }: { label: string; keyName: "primary_color" | "secondary_color" }) {
    const value = brand[keyName];
    return (
      <div>
        <p className="mb-1.5 text-[11px] font-medium text-white/40">{label}</p>
        <div className="flex items-center gap-2">
          <label className="relative h-9 w-9 shrink-0 cursor-pointer overflow-hidden rounded-lg border border-white/[0.1]" style={{ background: value || "transparent" }}>
            <input type="color" value={value || "#000000"} onChange={(e) => setBrand((b) => ({ ...b, [keyName]: e.target.value }))} className="absolute inset-0 cursor-pointer opacity-0" />
          </label>
          <input value={value} onChange={(e) => setBrand((b) => ({ ...b, [keyName]: e.target.value }))} placeholder="#a855f7" className="w-28 rounded-lg border border-white/[0.06] bg-white/[0.03] px-2.5 py-2 text-[12px] text-white/80 placeholder:text-white/20 focus:border-[#a855f7]/40" />
          <div className="flex flex-wrap gap-1">
            {SWATCHES.map((c) => (
              <button key={c} type="button" onClick={() => setBrand((b) => ({ ...b, [keyName]: c }))} className="h-5 w-5 rounded-md border border-white/10 transition-transform hover:scale-110" style={{ background: c }} />
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-slide-up">
      {/* ── Instagram ─────────────────────────────────────── */}
      <section className="glass rounded-2xl p-5 sm:p-6">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-white/25">Instagram</p>
        <p className="mt-1 text-[12px] text-white/40">Conecte para publicar vídeos, posts e carrosséis direto no Instagram.</p>

        <div className="mt-4">
          {igStatus?.connected ? (
            <div className="flex items-center justify-between rounded-xl bg-white/[0.03] px-4 py-3">
              <div className="flex items-center gap-3">
                {igStatus.profile_picture_url && (
                  <img src={igStatus.profile_picture_url} alt="" className="h-10 w-10 rounded-full ring-2 ring-[#dd2a7b]/40" />
                )}
                <div>
                  <p className="text-[14px] font-medium text-white/80">{igStatus.name}</p>
                  <p className="text-[11px] text-white/30">Conta conectada</p>
                </div>
                <span className="inline-flex items-center gap-1 rounded-full bg-green-500/20 px-2 py-0.5 text-[10px] font-medium text-green-400">
                  <span className="h-1.5 w-1.5 rounded-full bg-green-400" />
                  Ativo
                </span>
              </div>
              <button onClick={() => disconnect.mutate()} className="rounded-lg px-3 py-1.5 text-[12px] text-white/30 transition hover:bg-white/[0.06] hover:text-red-400">
                Desconectar
              </button>
            </div>
          ) : (
            <a
              href={instagramConnectUrl(workspace.id)}
              className="flex items-center justify-center gap-2.5 rounded-xl bg-gradient-to-r from-[#f58529] via-[#dd2a7b] to-[#8134af] px-5 py-3 text-[13px] font-semibold text-white transition hover:opacity-90"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="white">
                <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z" />
              </svg>
              Conectar Instagram
            </a>
          )}
        </div>
      </section>

      {/* ── Contexto ──────────────────────────────────────── */}
      <section className="glass rounded-2xl p-5 sm:p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-white/25">Contexto do projeto</p>
            <p className="mt-1 text-[12px] text-white/40">A IA usa este texto em todos os vídeos e posts.</p>
          </div>
          {!editingContext && (
            <button onClick={() => { setDraftDescription(workspace.description); setEditingContext(true); }} className="text-[12px] font-medium text-[#c084fc] hover:text-[#d8b4fe]">
              Editar
            </button>
          )}
        </div>

        <div className="mt-4">
          {editingContext ? (
            <div className="space-y-2">
              <textarea
                value={draftDescription}
                onChange={(e) => setDraftDescription(e.target.value)}
                rows={7}
                autoFocus
                className="w-full resize-none rounded-xl border border-white/[0.06] bg-white/[0.03] p-3.5 text-[13px] leading-relaxed text-white/90 transition-all focus:border-[#a855f7]/40 focus:bg-white/[0.05]"
              />
              <div className="flex justify-end gap-2">
                <button onClick={() => setEditingContext(false)} className="rounded-lg px-3 py-1.5 text-[12px] text-white/40 hover:text-white/70">Cancelar</button>
                <button onClick={() => saveContext.mutate()} disabled={saveContext.isPending} className="btn-gradient rounded-lg px-4 py-1.5 text-[12px] font-semibold text-white disabled:opacity-40">
                  {saveContext.isPending ? "Salvando..." : "Salvar"}
                </button>
              </div>
            </div>
          ) : (
            <p className="whitespace-pre-line rounded-xl bg-white/[0.02] p-3.5 text-[13px] leading-relaxed text-white/50">
              {workspace.description || "Sem contexto ainda. Descreva a marca, público, tom de voz e objetivos."}
            </p>
          )}
        </div>
      </section>

      {/* ── Identidade visual ─────────────────────────────── */}
      <section className="glass rounded-2xl p-5 sm:p-6">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-white/25">Identidade visual</p>
        <p className="mt-1 text-[12px] text-white/40">Logo, cores e estilo aplicados nas artes dos posts e imagens geradas pela IA.</p>

        <div className="mt-4 grid gap-5 sm:grid-cols-[auto_1fr]">
          <div>
            <p className="mb-1.5 text-[11px] font-medium text-white/40">Logo</p>
            <input ref={logoInputRef} type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadLogo.mutate(f); e.target.value = ""; }} className="hidden" />
            <div className="flex flex-col items-center gap-2">
              <button type="button" onClick={() => logoInputRef.current?.click()} className="flex h-28 w-28 items-center justify-center overflow-hidden rounded-2xl border border-dashed border-white/[0.14] bg-[repeating-conic-gradient(#ffffff08_0%_25%,transparent_0%_50%)] bg-[length:16px_16px] transition-all hover:border-[#a855f7]/40">
                {workspace.logo_path ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={mediaUrl(workspace.logo_path)} alt="Logo" className="max-h-full max-w-full object-contain p-2" />
                ) : (
                  <span className="px-2 text-center text-[10px] text-white/30">{uploadLogo.isPending ? "Enviando..." : "Enviar logo (PNG)"}</span>
                )}
              </button>
              <div className="flex gap-2 text-[10px]">
                <button type="button" onClick={() => logoInputRef.current?.click()} className="text-[#c084fc] hover:text-[#d8b4fe]">Trocar</button>
                {workspace.logo_path && (
                  <button type="button" onClick={() => removeLogo.mutate()} className="text-white/30 hover:text-[#ff453a]">Remover</button>
                )}
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex flex-wrap gap-x-6 gap-y-4">
              <ColorField label="Cor principal" keyName="primary_color" />
              <ColorField label="Cor secundária" keyName="secondary_color" />
            </div>

            <div>
              <p className="mb-1.5 text-[11px] font-medium text-white/40">Fundo das artes</p>
              <div className="flex gap-1.5 rounded-xl bg-white/[0.04] p-1 sm:w-fit">
                {([{ id: "dark", label: "Escuro" }, { id: "light", label: "Claro" }] as const).map((t) => (
                  <button key={t.id} type="button" onClick={() => setBrand((b) => ({ ...b, text_theme: t.id }))} className={`rounded-lg px-4 py-1.5 text-[12px] font-semibold transition-all ${brand.text_theme === t.id ? "bg-gradient-to-br from-[#a855f7] to-[#ec4899] text-white" : "text-white/40 hover:text-white/70"}`}>
                    {t.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <p className="mb-1.5 text-[11px] font-medium text-white/40">Estilo visual</p>
              <textarea value={brand.visual_style} onChange={(e) => setBrand((b) => ({ ...b, visual_style: e.target.value }))} rows={2} placeholder="Ex.: fotografia editorial escura, alto contraste, tons de verde e dourado, minimalista" className="w-full resize-none rounded-xl border border-white/[0.06] bg-white/[0.03] p-3 text-[12px] leading-relaxed text-white/80 placeholder:text-white/20 focus:border-[#a855f7]/40" />
            </div>

            {brandDirty && (
              <div className="flex justify-end">
                <button onClick={() => saveBrand.mutate()} disabled={saveBrand.isPending} className="btn-gradient rounded-lg px-4 py-1.5 text-[12px] font-semibold text-white disabled:opacity-40">
                  {saveBrand.isPending ? "Salvando..." : "Salvar identidade"}
                </button>
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

// ── Página principal ─────────────────────────────────────────────────

export default function WorkspacePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const workspaceId = Number(id);
  const router = useRouter();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<TabId>("videos");

  const { data: workspace, error } = useQuery({
    queryKey: ["workspace", workspaceId],
    queryFn: () => api.getWorkspace(workspaceId),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 4_000;
      const active =
        data.posts.some((p) => p.status === "queued" || p.status === "running") ||
        data.projects.some((p) => p.status === "queued" || p.status === "running");
      return active ? 4_000 : false;
    },
  });

  const { data: igStatus } = useQuery({
    queryKey: ["instagram_status", workspaceId],
    queryFn: () => api.getInstagramStatus(workspaceId),
    staleTime: 30_000,
  });
  const igConnected = !!igStatus?.connected;

  const removeWorkspace = useMutation({
    mutationFn: () => api.deleteWorkspace(workspaceId),
    onSuccess: () => router.push("/workspaces"),
  });

  if (error) {
    return (
      <div className="mx-auto max-w-[980px] px-4 pt-8 sm:px-6">
        <p className="rounded-xl bg-[--red-soft] px-4 py-3 text-[13px] text-[#ff453a]">
          {error instanceof Error ? error.message : "Erro ao carregar o projeto"}
        </p>
      </div>
    );
  }
  if (!workspace) {
    return (
      <div className="flex justify-center pt-20">
        <svg className="h-6 w-6 animate-spin text-white/30" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" className="opacity-25" />
          <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
        </svg>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[980px] space-y-5 px-4 pb-16 pt-2 animate-slide-up sm:px-6">
      {/* ── Header ────────────────────────────────────────── */}
      <div className="glass rounded-2xl p-5 sm:rounded-3xl sm:p-6">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            {workspace.logo_path ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={mediaUrl(workspace.logo_path)} alt="" className="h-10 w-10 shrink-0 rounded-xl object-contain" />
            ) : (
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-[#a855f7] to-[#ec4899]">
                <span className="text-[16px] font-bold text-white">{workspace.name.charAt(0)}</span>
              </div>
            )}
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="truncate text-lg font-semibold tracking-tight sm:text-xl">{workspace.name}</h1>
                {igConnected && igStatus?.name && (
                  <span className="hidden shrink-0 items-center gap-1.5 rounded-full bg-gradient-to-r from-[#f58529]/10 via-[#dd2a7b]/10 to-[#8134af]/10 px-2.5 py-0.5 text-[10px] font-medium text-[#dd2a7b] sm:inline-flex">
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069z" /></svg>
                    {igStatus.name}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-3 text-[11px] text-white/30 sm:text-[12px]">
                <Link href="/workspaces" className="transition-colors hover:text-white/60">‹ Projetos</Link>
                <span>{workspace.projects.length} vídeo{workspace.projects.length === 1 ? "" : "s"}</span>
                <span>{workspace.posts.length} post{workspace.posts.length === 1 ? "" : "s"}</span>
              </div>
            </div>
          </div>
          <button
            onClick={() => { if (confirm("Excluir este projeto e seus posts?")) removeWorkspace.mutate(); }}
            className="shrink-0 rounded-lg px-2.5 py-1.5 text-[11px] text-white/20 transition-colors hover:text-[#ff453a]"
          >
            Excluir
          </button>
        </div>
      </div>

      {/* ── Tabs ──────────────────────────────────────────── */}
      <div className="flex gap-1 rounded-xl bg-white/[0.03] p-1">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-3 py-2.5 text-[12px] font-semibold transition-all sm:text-[13px] ${
              activeTab === tab.id
                ? "bg-gradient-to-br from-[#a855f7] to-[#ec4899] text-white shadow-lg shadow-[#a855f7]/20"
                : "text-white/40 hover:text-white/70"
            }`}
          >
            {tab.icon}
            <span className="hidden sm:inline">{tab.label}</span>
            <span className="sm:hidden">{tab.short}</span>
          </button>
        ))}
      </div>

      {/* ── Tab content ───────────────────────────────────── */}
      {activeTab === "videos" && <VideosTab workspace={workspace} />}
      {activeTab === "posts" && <PostsTab workspace={workspace} igConnected={igConnected} />}
      {activeTab === "calendar" && <CalendarTab workspaceId={workspaceId} />}
      {activeTab === "settings" && <SettingsTab workspace={workspace} />}
    </div>
  );
}
