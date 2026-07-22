"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  api,
  EDIT_ASPECTS,
  EDIT_AUDIO_OPTIONS,
  isActive,
  LANGUAGES,
  mediaUrl,
  Project,
} from "@/lib/api";

const MODE_TAGS: Record<string, string> = {
  creative: "Criativo · ",
  edit: "Edição · ",
};
import { LibraryPickerModal, LibrarySection } from "@/components/Library";

const STATUS_CONFIG: Record<string, { label: string; shortLabel: string; color: string; bg: string; dot: string }> = {
  draft: {
    label: "Rascunho",
    shortLabel: "Rascunho",
    color: "text-white/50",
    bg: "bg-white/[0.06]",
    dot: "bg-white/30",
  },
  queued: {
    label: "Na fila",
    shortLabel: "Fila",
    color: "text-[#64d2ff]",
    bg: "bg-[--cyan-soft]",
    dot: "bg-[#64d2ff]",
  },
  running: {
    label: "Processando",
    shortLabel: "Proc.",
    color: "text-[#ff9f0a]",
    bg: "bg-[--orange-soft]",
    dot: "bg-[#ff9f0a] animate-shimmer",
  },
  awaiting_review: {
    label: "Aguardando revisão",
    shortLabel: "Revisão",
    color: "text-[#bf5af2]",
    bg: "bg-[--purple-soft]",
    dot: "bg-[#bf5af2] animate-pulse-ring",
  },
  completed: {
    label: "Concluído",
    shortLabel: "OK",
    color: "text-[#30d158]",
    bg: "bg-[--green-soft]",
    dot: "bg-[#30d158]",
  },
  failed: {
    label: "Falhou",
    shortLabel: "Erro",
    color: "text-[#ff453a]",
    bg: "bg-[--red-soft]",
    dot: "bg-[#ff453a]",
  },
};

function StatusBadge({ status }: { status: string }) {
  const config = STATUS_CONFIG[status] ?? {
    label: status,
    shortLabel: status,
    color: "text-white/50",
    bg: "bg-white/[0.06]",
    dot: "bg-white/30",
  };
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-medium sm:px-2.5 sm:py-1 sm:text-[11px] ${config.bg} ${config.color}`}>
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${config.dot}`} />
      <span className="hidden sm:inline">{config.label}</span>
      <span className="sm:hidden">{config.shortLabel}</span>
    </span>
  );
}

export default function DashboardPage() {
  return (
    <Suspense>
      <Dashboard />
    </Suspense>
  );
}

function Dashboard() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const searchParams = useSearchParams();
  const workspaceId = Number(searchParams.get("workspace")) || null;
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<"generative" | "creative" | "edit">("generative");
  const [topic, setTopic] = useState("");
  const [style, setStyle] = useState("");
  const [editStyle, setEditStyle] = useState("vlog");
  const [aspect, setAspect] = useState("original");
  const [audioEnhance, setAudioEnhance] = useState("full");
  const [transition, setTransition] = useState("auto");
  const [language, setLanguage] = useState("pt-BR");
  const [review, setReview] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [libraryIds, setLibraryIds] = useState<number[]>([]);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [uploading, setUploading] = useState(false);

  // Sem workspace vinculado, redireciona para projetos
  useEffect(() => {
    if (!workspaceId) router.replace("/workspaces");
  }, [workspaceId, router]);

  const {
    data: projects = [],
    error,
  } = useQuery({
    queryKey: ["projects"],
    queryFn: api.listProjects,
    refetchInterval: (query) => {
      const data = query.state.data as Project[] | undefined;
      if (!data) return 5_000;
      const hasActive = data.some((p) => isActive(p.status));
      return hasActive ? 5_000 : false;
    },
  });

  const { data: linkedWorkspace } = useQuery({
    queryKey: ["workspace", workspaceId],
    queryFn: () => api.getWorkspace(workspaceId!),
    enabled: workspaceId != null,
  });

  const { data: editStyles = [] } = useQuery({
    queryKey: ["edit-styles"],
    queryFn: api.listEditStyles,
    enabled: mode === "edit",
    staleTime: Infinity,
  });

  const { data: editTransitions = [] } = useQuery({
    queryKey: ["edit-transitions"],
    queryFn: api.listEditTransitions,
    enabled: mode === "edit",
    staleTime: Infinity,
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      const config: Record<string, unknown> = {};
      if (style.trim()) config.style_preset = style.trim();
      if (mode !== "edit" && review) config.review_stages = ["script", "images"];
      if (mode === "edit") {
        config.edit_style = editStyle;
        config.aspect = aspect;
        config.audio_enhance = audioEnhance;
        config.transition = transition;
      }
      const project = await api.createProject({
        topic: topic.trim() || "Edição automática de vídeo bruto",
        mode,
        language,
        config,
        autostart: mode === "generative",
        workspace_id: workspaceId,
      });
      if (mode !== "generative") {
        setUploading(true);
        try {
          if (files.length > 0) await api.uploadSources(project.id, files);
          if (libraryIds.length > 0) await api.attachFromLibrary(project.id, libraryIds);
        } finally {
          setUploading(false);
        }
      }
      return project;
    },
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      queryClient.invalidateQueries({ queryKey: ["library"] });
      if (workspaceId != null)
        queryClient.invalidateQueries({ queryKey: ["workspace", workspaceId] });
      setTopic("");
      setFiles([]);
      setLibraryIds([]);
      if (mode !== "generative") router.push(`/projects/${project.id}`);
    },
  });

  function handleCreate(event: React.FormEvent) {
    event.preventDefault();
    if (mode === "edit") {
      if (files.length === 0 && libraryIds.length === 0) return;
    } else if (!topic.trim()) {
      return;
    }
    createMutation.mutate();
  }

  function addFiles(list: FileList | null) {
    if (!list) return;
    // Materializa já: a FileList é "viva" e esvazia quando o input é resetado
    const items = Array.from(list);
    if (items.length === 0) return;
    setFiles((prev) => [...prev, ...items]);
  }

  const errorMessage =
    createMutation.error?.message ?? (error instanceof Error ? error.message : null);

  if (!workspaceId) return null;

  return (
    <div className="mx-auto max-w-[980px] space-y-8 px-4 pb-16 pt-2 animate-slide-up sm:space-y-10 sm:px-6">
      {/* ── Hero / Create ─────────────────────────────────────── */}
      <section className="glass rounded-2xl p-5 shadow-xl shadow-black/10 sm:rounded-3xl sm:p-8">
        <div className="flex items-center gap-3 mb-1">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-[#a855f7] to-[#ec4899] shadow-[inset_0_1px_0_rgba(255,255,255,0.25)] sm:h-10 sm:w-10 sm:rounded-2xl">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="sm:h-[18px] sm:w-[18px]">
              <path d="M12 5v14M5 12h14" />
            </svg>
          </div>
          <div className="min-w-0">
            <h1 className="text-lg font-semibold tracking-tight sm:text-xl">
              {mode === "generative"
                ? "Novo vídeo"
                : mode === "creative"
                  ? "Novo criativo"
                  : "Edição mágica"}
            </h1>
            <p className="text-[12px] text-white/40 sm:text-[13px]">
              {mode === "generative"
                ? "Descreva o tema e a IA cria tudo automaticamente."
                : mode === "creative"
                  ? "Envie seus vídeos/fotos, descreva o produto e a IA monta o anúncio."
                  : "Envie o vídeo bruto e a IA corta erros, silêncios e retakes sozinha."}
            </p>
          </div>
        </div>

        {linkedWorkspace && (
          <div className="mt-3 flex items-center gap-2 rounded-xl bg-[--purple-soft] px-3.5 py-2.5 text-[12px] text-[#d8b4fe]">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
            </svg>
            <span>
              Criando no projeto <strong>{linkedWorkspace.name}</strong> — a IA usa o contexto dele como referência.
            </span>
            <Link
              href={`/workspaces/${linkedWorkspace.id}`}
              className="ml-auto shrink-0 font-semibold text-[#c084fc] hover:text-white"
            >
              Ver projeto
            </Link>
          </div>
        )}

        {/* Mode selector */}
        <div className="mt-4 flex gap-1.5 rounded-xl bg-white/[0.04] p-1 sm:w-fit">
          {(
            [
              { id: "generative", label: "Vídeo rápido", hint: "só com o tema" },
              { id: "creative", label: "Criativo (anúncio)", hint: "com sua mídia" },
              { id: "edit", label: "Edição mágica", hint: "vídeo bruto" },
            ] as const
          ).map((m) => (
            <button
              key={m.id}
              type="button"
              onClick={() => setMode(m.id)}
              className={`flex-1 rounded-lg px-4 py-2 text-[12px] font-semibold transition-all sm:flex-none sm:text-[13px] ${
                mode === m.id
                  ? "bg-gradient-to-br from-[#a855f7] to-[#ec4899] text-white shadow-lg shadow-[#a855f7]/20"
                  : "text-white/40 hover:text-white/70"
              }`}
            >
              {m.label}
              <span className={`ml-1.5 hidden text-[10px] font-normal sm:inline ${mode === m.id ? "text-white/70" : "text-white/25"}`}>
                {m.hint}
              </span>
            </button>
          ))}
        </div>

        <form onSubmit={handleCreate} className="mt-4 space-y-3 sm:mt-5 sm:space-y-4">
          <textarea
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder={
              mode === "generative"
                ? "Ex.: 5 curiosidades sobre o Império Romano que quase ninguém conhece"
                : mode === "creative"
                  ? "Brief do criativo — produto, público, oferta e dor que ele resolve. Ex.: Tênis de corrida X-Run, para corredores amadores; dor: joelho ao correr; oferta: 20% off no site."
                  : "Título do projeto (opcional). Dica de gravação: errou? Fale \"corta\" e repita a frase. Para descartar um trecho inteiro, fale \"corta\" no início e \"retoma\" no fim."
            }
            rows={3}
            className="w-full resize-none rounded-xl border border-white/[0.06] bg-white/[0.03] p-3.5 text-[14px] leading-relaxed text-white/90 placeholder:text-white/20 transition-all duration-300 focus:border-[#a855f7]/40 focus:bg-white/[0.05] focus:shadow-[0_0_0_4px_rgba(168,85,247,0.08)] sm:rounded-2xl sm:p-4"
          />

          {mode === "edit" && (
            <div className="space-y-4">
            <div>
            <p className="mb-1.5 px-0.5 text-[10px] font-semibold uppercase tracking-widest text-white/25">
              Estilo de edição
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              {(editStyles.length > 0
                ? editStyles
                : [
                    { id: "dynamic", label: "Dinâmico (TikTok/Reels)", description: "Jump cuts agressivos, zero ar morto, punch-in de zoom." },
                    { id: "vlog", label: "Vlog (YouTube casual)", description: "Cortes de ritmo médio com crossfades suaves." },
                    { id: "clean", label: "Educacional / Clean", description: "Remove só o ar morto longo; preserva o ritmo natural." },
                    { id: "podcast", label: "Podcast / Longform", description: "Só limpeza de silêncios longos e erros marcados." },
                  ]
              ).map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setEditStyle(s.id)}
                  className={`rounded-xl border p-3 text-left transition-all sm:p-3.5 ${
                    editStyle === s.id
                      ? "border-[#a855f7]/50 bg-[--accent-soft] shadow-[0_0_0_3px_rgba(168,85,247,0.08)]"
                      : "border-white/[0.06] bg-white/[0.02] hover:border-white/15 hover:bg-white/[0.04]"
                  }`}
                >
                  <span className={`block text-[12px] font-semibold sm:text-[13px] ${editStyle === s.id ? "text-[#d8b4fe]" : "text-white/70"}`}>
                    {s.label}
                  </span>
                  <span className="mt-0.5 block text-[10px] leading-relaxed text-white/35 sm:text-[11px]">
                    {s.description}
                  </span>
                </button>
              ))}
            </div>
            </div>

            {/* Formato / plataforma */}
            <div>
              <p className="mb-1.5 px-0.5 text-[10px] font-semibold uppercase tracking-widest text-white/25">
                Formato de saída
              </p>
              <div className="flex flex-wrap gap-1.5">
                {EDIT_ASPECTS.map((a) => (
                  <button
                    key={a.id}
                    type="button"
                    onClick={() => setAspect(a.id)}
                    className={`rounded-lg border px-3 py-2 text-left transition-all ${
                      aspect === a.id
                        ? "border-[#a855f7]/50 bg-[--accent-soft]"
                        : "border-white/[0.06] bg-white/[0.02] hover:border-white/15"
                    }`}
                  >
                    <span className={`block text-[11px] font-semibold ${aspect === a.id ? "text-[#d8b4fe]" : "text-white/60"}`}>
                      {a.label}
                    </span>
                    <span className="block text-[9px] text-white/30">{a.hint}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Tratamento de áudio */}
            <div>
              <p className="mb-1.5 px-0.5 text-[10px] font-semibold uppercase tracking-widest text-white/25">
                Tratamento de áudio
              </p>
              <div className="flex flex-wrap gap-1.5">
                {EDIT_AUDIO_OPTIONS.map((a) => (
                  <button
                    key={a.id}
                    type="button"
                    onClick={() => setAudioEnhance(a.id)}
                    className={`rounded-lg border px-3 py-2 text-left transition-all ${
                      audioEnhance === a.id
                        ? "border-[#a855f7]/50 bg-[--accent-soft]"
                        : "border-white/[0.06] bg-white/[0.02] hover:border-white/15"
                    }`}
                  >
                    <span className={`block text-[11px] font-semibold ${audioEnhance === a.id ? "text-[#d8b4fe]" : "text-white/60"}`}>
                      {a.label}
                    </span>
                    <span className="block text-[9px] text-white/30">{a.hint}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Transição dos cortes (com prévia em vídeo) */}
            {editTransitions.length > 0 && (
              <div>
                <p className="mb-1.5 px-0.5 text-[10px] font-semibold uppercase tracking-widest text-white/25">
                  Transição dos cortes
                  <span className="ml-2 font-normal normal-case tracking-normal text-white/20">
                    aplicada quando um trecho grande é removido
                  </span>
                </p>
                <div className="flex gap-2 overflow-x-auto pb-1.5 scrollbar-hide">
                  {editTransitions.map((t) => (
                    <button
                      key={t.id}
                      type="button"
                      onClick={() => setTransition(t.id)}
                      title={t.description}
                      className={`w-28 shrink-0 overflow-hidden rounded-xl border text-left transition-all sm:w-32 ${
                        transition === t.id
                          ? "border-[#a855f7]/60 shadow-[0_0_0_3px_rgba(168,85,247,0.12)]"
                          : "border-white/[0.06] hover:border-white/20"
                      }`}
                    >
                      <div className="aspect-video w-full bg-black/40">
                        {t.preview_path ? (
                          <video
                            src={mediaUrl(t.preview_path)}
                            autoPlay
                            loop
                            muted
                            playsInline
                            className="h-full w-full object-cover"
                          />
                        ) : (
                          <div className="flex h-full w-full items-center justify-center">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-white/25">
                              <path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1" />
                            </svg>
                          </div>
                        )}
                      </div>
                      <span
                        className={`block px-2 py-1.5 text-[10px] font-semibold ${
                          transition === t.id ? "bg-[--accent-soft] text-[#d8b4fe]" : "bg-white/[0.02] text-white/55"
                        }`}
                      >
                        {t.label}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}
            </div>
          )}

          {(mode === "creative" || mode === "edit") && (
            <div>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept={mode === "edit" ? "video/*" : "video/*,image/*"}
                onChange={(e) => {
                  addFiles(e.target.files);
                  e.target.value = "";
                }}
                className="hidden"
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  addFiles(e.dataTransfer.files);
                }}
                className="flex w-full flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-white/[0.12] bg-white/[0.02] px-4 py-6 text-center transition-all hover:border-[#a855f7]/40 hover:bg-white/[0.04] sm:rounded-2xl sm:py-8"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-white/30">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
                <span className="text-[13px] font-medium text-white/60">
                  {mode === "edit"
                    ? "Arraste o vídeo bruto aqui, ou clique para escolher"
                    : "Arraste vídeos e fotos aqui, ou clique para escolher"}
                </span>
                <span className="text-[11px] text-white/25">
                  {mode === "edit"
                    ? "A IA transcreve tudo, detecta \"corta\", retakes, silêncios e vícios de fala — e monta o corte final."
                    : "Shorts, gravações do produto, unboxings, depoimentos... A IA quebra em trechos e escolhe os melhores."}
                </span>
              </button>

              <div className="mt-2 flex items-center justify-between px-0.5">
                <button
                  type="button"
                  onClick={() => setLibraryOpen(true)}
                  className="text-[11px] font-medium text-[#c084fc] hover:text-[#d8b4fe]"
                >
                  Ou escolher da biblioteca
                  {libraryIds.length > 0 ? ` (${libraryIds.length})` : ""}
                </button>
                {libraryIds.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setLibraryIds([])}
                    className="text-[11px] text-white/30 hover:text-[#ff453a]"
                  >
                    Limpar seleção
                  </button>
                )}
              </div>

              {files.length > 0 && (
                <div className="mt-2.5 flex flex-wrap gap-2">
                  {files.map((file, i) => (
                    <span
                      key={`${file.name}-${i}`}
                      className="flex items-center gap-2 rounded-lg bg-white/[0.06] px-2.5 py-1.5 text-[11px] text-white/60"
                    >
                      {file.name}
                      <span className="text-white/25">{(file.size / 1024 / 1024).toFixed(1)} MB</span>
                      <button
                        type="button"
                        onClick={() => setFiles((prev) => prev.filter((_, j) => j !== i))}
                        className="text-white/30 transition-colors hover:text-[#ff453a]"
                      >
                        ✕
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="w-full appearance-none rounded-xl border border-white/[0.06] bg-white/[0.03] px-3.5 py-3 text-[14px] text-white/90 transition-all duration-300 focus:border-[#a855f7]/40 focus:bg-white/[0.05] sm:w-auto sm:text-[13px] [&>option]:bg-[#16161a]"
            >
              {LANGUAGES.map((l) => (
                <option key={l.value} value={l.value}>
                  {l.label}
                </option>
              ))}
            </select>
            {mode === "generative" && (
              <input
                value={style}
                onChange={(e) => setStyle(e.target.value)}
                placeholder="Estilo visual (opcional) — ex.: cinematic dark fantasy"
                className="w-full rounded-xl border border-white/[0.06] bg-white/[0.03] px-3.5 py-3 text-[14px] text-white/90 placeholder:text-white/20 transition-all duration-300 focus:border-[#a855f7]/40 focus:bg-white/[0.05] focus:shadow-[0_0_0_4px_rgba(168,85,247,0.08)] sm:min-w-64 sm:flex-1 sm:text-[13px]"
              />
            )}
            <div className="flex items-center gap-3 sm:ml-auto">
              {mode !== "edit" ? (
                <label className="flex flex-1 cursor-pointer items-center gap-2.5 rounded-xl border border-white/[0.06] bg-white/[0.03] px-3.5 py-3 text-[13px] text-white/50 transition-all hover:bg-white/[0.06] active:bg-white/[0.06] select-none sm:flex-none sm:px-4">
                  <div className="relative shrink-0">
                    <input
                      type="checkbox"
                      checked={review}
                      onChange={(e) => setReview(e.target.checked)}
                      className="peer sr-only"
                    />
                    <div className="h-5 w-9 rounded-full bg-white/10 transition-colors peer-checked:bg-[#30d158]" />
                    <div className="absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-transform peer-checked:translate-x-4" />
                  </div>
                  Revisar antes
                </label>
              ) : (
                <span className="flex-1 text-[11px] leading-snug text-white/30 sm:max-w-52 sm:flex-none">
                  Você revisa os cortes sugeridos antes do render final.
                </span>
              )}
              <button
                type="submit"
                disabled={
                  createMutation.isPending ||
                  (mode === "edit"
                    ? files.length === 0 && libraryIds.length === 0
                    : !topic.trim())
                }
                className="btn-gradient shrink-0 rounded-xl px-5 py-3 text-[13px] font-semibold text-white shadow-lg shadow-[#a855f7]/20 disabled:opacity-30 disabled:shadow-none sm:px-6"
              >
                {createMutation.isPending ? (
                  <span className="flex items-center gap-2">
                    <svg className="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
                      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="32" strokeDashoffset="32" className="opacity-25" />
                      <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
                    </svg>
                    {uploading ? "Enviando mídia..." : "Criando..."}
                  </span>
                ) : mode === "generative" ? (
                  "Criar vídeo"
                ) : mode === "creative" ? (
                  "Criar criativo"
                ) : (
                  "Editar vídeo"
                )}
              </button>
            </div>
          </div>
        </form>

        {errorMessage && (
          <div className="mt-4 flex items-start gap-2 rounded-xl bg-[--red-soft] px-3.5 py-3 text-[12px] text-[#ff453a] sm:items-center sm:text-[13px]">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mt-0.5 shrink-0 sm:mt-0">
              <circle cx="12" cy="12" r="10" /><path d="M12 8v4M12 16h.01" />
            </svg>
            {errorMessage}
          </div>
        )}
      </section>

      {/* ── Project List ──────────────────────────────────────── */}
      <section className="space-y-3 sm:space-y-4">
        <div className="flex items-center justify-between px-1">
          <h2 className="text-[12px] font-semibold uppercase tracking-widest text-white/30 sm:text-[13px]">
            Projetos
          </h2>
          {projects.length > 0 && (
            <span className="text-[11px] text-white/25 sm:text-[12px]">{projects.length}</span>
          )}
        </div>

        {projects.length === 0 ? (
          <div className="glass flex flex-col items-center justify-center rounded-2xl py-12 text-center sm:rounded-3xl sm:py-16">
            <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-white/[0.04] sm:mb-4 sm:h-14 sm:w-14">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-white/20 sm:h-6 sm:w-6">
                <rect x="2" y="2" width="20" height="20" rx="5" />
                <path d="M10 9l4 3-4 3V9z" />
              </svg>
            </div>
            <p className="text-[13px] font-medium text-white/30 sm:text-[14px]">Nenhum projeto ainda</p>
            <p className="mt-1 text-[11px] text-white/20 sm:text-[12px]">Crie o primeiro acima para começar.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {projects.map((project, i) => (
              <Link
                key={project.id}
                href={`/projects/${project.id}`}
                className="glass glass-hover group flex items-center justify-between gap-3 rounded-xl px-3.5 py-3.5 transition-all duration-300 animate-slide-up sm:rounded-2xl sm:px-5 sm:py-4"
                style={{ animationDelay: `${i * 50}ms` }}
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[14px] font-medium tracking-tight text-white/90 transition-colors group-hover:text-white sm:text-[15px]">
                    {project.title ?? project.topic}
                  </p>
                  <p className="mt-0.5 truncate text-[11px] text-white/25 sm:mt-1 sm:text-[12px]">
                    #{project.id} · {MODE_TAGS[project.mode] ?? ""}
                    {new Date(project.created_at).toLocaleString("pt-BR")}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2 sm:gap-3">
                  <StatusBadge status={project.status} />
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-white/15 transition-all group-hover:translate-x-0.5 group-hover:text-white/30 sm:h-4 sm:w-4">
                    <polyline points="9 18 15 12 9 6" />
                  </svg>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>

      <LibrarySection />

      <LibraryPickerModal
        open={libraryOpen}
        onClose={() => setLibraryOpen(false)}
        onConfirm={(ids) => {
          setLibraryIds(ids);
        }}
        confirmLabel="Usar nestes criativos"
      />
    </div>
  );
}
