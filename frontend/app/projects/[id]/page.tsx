"use client";

import { use, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Asset,
  EditCut,
  InstagramStatus,
  ProjectDetail,
  PublicationResponse,
  Scene,
  SourceAsset,
  SourceSegment,
  StageRun,
  api,
  instagramConnectUrl,
  isActive,
  mediaUrl,
  shouldPollPublications,
  stageLabels,
  stageOrder,
} from "@/lib/api";
import { LibraryPickerModal } from "@/components/Library";
import InsightsPanel from "@/components/InsightsPanel";

// ── Icons ────────────────────────────────────────────────────────────

function IconCheck({ className = "" }: { className?: string }) {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function IconX({ className = "" }: { className?: string }) {
  return (
    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

// ── Pipeline progress ────────────────────────────────────────────────

function stageStatus(status: string | undefined) {
  switch (status) {
    case "done":
      return {
        icon: <IconCheck className="text-[#30d158]" />,
        ring: "border-[#30d158]/30 bg-[--green-soft]",
        text: "text-[#30d158]",
        line: "bg-[#30d158]/40",
      };
    case "running":
      return {
        icon: <span className="h-2 w-2 rounded-full bg-[#ff9f0a] animate-shimmer" />,
        ring: "border-[#ff9f0a]/30 bg-[--orange-soft]",
        text: "text-[#ff9f0a]",
        line: "bg-[#ff9f0a]/30",
      };
    case "failed":
      return {
        icon: <IconX className="text-[#ff453a]" />,
        ring: "border-[#ff453a]/30 bg-[--red-soft]",
        text: "text-[#ff453a]",
        line: "bg-[#ff453a]/30",
      };
    case "awaiting_review":
      return {
        icon: <span className="h-2 w-2 rounded-full bg-[#bf5af2] animate-pulse-ring" />,
        ring: "border-[#bf5af2]/30 bg-[--purple-soft]",
        text: "text-[#bf5af2]",
        line: "bg-[#bf5af2]/30",
      };
    default:
      return {
        icon: <span className="h-1.5 w-1.5 rounded-full bg-white/15" />,
        ring: "border-white/[0.06] bg-white/[0.02]",
        text: "text-white/25",
        line: "bg-white/[0.06]",
      };
  }
}

function PipelineProgress({
  stages,
  labels,
  order,
}: {
  stages: StageRun[];
  labels: Record<string, string>;
  order: string[];
}) {
  const byStage = useMemo(() => {
    const map = new Map<string, StageRun>();
    for (const run of stages) map.set(run.stage, run);
    return map;
  }, [stages]);

  return (
    <div className="glass rounded-xl p-3.5 sm:rounded-2xl sm:p-5">
      {/* Mobile: scrollable row */}
      <div className="flex items-center gap-1 overflow-x-auto scrollbar-hide pb-1 sm:pb-0">
        {order.map((name, i) => {
          const run = byStage.get(name);
          const s = stageStatus(run?.status);
          return (
            <div key={name} className="flex shrink-0 items-center">
              <div
                title={run?.error ?? undefined}
                className="flex flex-col items-center gap-1.5 sm:gap-2"
              >
                <div className={`flex h-7 w-7 items-center justify-center rounded-full border sm:h-8 sm:w-8 ${s.ring} transition-all duration-300`}>
                  {s.icon}
                </div>
                <span className={`whitespace-nowrap text-[9px] font-medium tracking-wide sm:text-[10px] ${s.text} transition-colors`}>
                  {labels[name]}
                </span>
              </div>
              {i < order.length - 1 && (
                <div className={`mx-1 mt-[-14px] h-px w-4 sm:mx-1.5 sm:mt-[-18px] sm:w-6 ${s.line} transition-colors`} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Scene card ───────────────────────────────────────────────────────

function SceneCard({
  project,
  scene,
  image,
  segmentThumb,
  onChanged,
}: {
  project: ProjectDetail;
  scene: Scene;
  image: Asset | undefined;
  segmentThumb: string | null;
  onChanged: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [prompt, setPrompt] = useState(scene.image_prompt ?? "");
  const usesSourceMedia = scene.visual_source === "segment" || scene.visual_source === "source_image";

  const regenMutation = useMutation({
    mutationFn: () =>
      api.regenerateImage(project.id, scene.id, editing ? prompt : undefined),
    onSuccess: () => {
      setEditing(false);
      onChanged();
    },
  });

  const timing =
    scene.start_time != null && scene.end_time != null
      ? `${scene.start_time.toFixed(1)}s – ${scene.end_time.toFixed(1)}s`
      : `~${scene.estimated_duration.toFixed(0)}s`;

  return (
    <div className="glass group overflow-hidden rounded-xl transition-all duration-300 hover:border-white/10 animate-scale-in sm:rounded-2xl">
      <div className="relative aspect-[2/3] bg-black/40 overflow-hidden">
        {image || (usesSourceMedia && segmentThumb) ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={mediaUrl(image ? image.path : segmentThumb!)}
            alt={`Cena ${scene.index + 1}`}
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
          />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white/[0.04]">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-white/15">
                <rect x="3" y="3" width="18" height="18" rx="4" />
                <circle cx="8.5" cy="8.5" r="1.5" />
                <path d="m21 15-5-5L5 21" />
              </svg>
            </div>
            <span className="text-[10px] text-white/20">Aguardando geração</span>
          </div>
        )}

        <div className="absolute inset-x-0 top-0 flex items-start justify-between p-2">
          <span className="rounded-md bg-black/60 backdrop-blur-md px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wider text-white/70 sm:rounded-lg sm:px-2 sm:py-1 sm:text-[10px]">
            {scene.role} · {timing}
          </span>
          {usesSourceMedia ? (
            <span className="rounded-md bg-[#30d158]/80 backdrop-blur-md px-1.5 py-0.5 text-[9px] font-semibold text-white sm:rounded-lg sm:px-2 sm:py-1 sm:text-[10px]">
              mídia real
            </span>
          ) : image ? (
            <span className="rounded-md bg-black/60 backdrop-blur-md px-1.5 py-0.5 text-[9px] font-medium text-white/50 sm:rounded-lg sm:px-2 sm:py-1 sm:text-[10px]">
              v{image.version}
            </span>
          ) : null}
        </div>
      </div>

      <div className="space-y-2.5 p-3 sm:space-y-3 sm:p-4">
        <p className="text-[11px] leading-relaxed text-white/55 sm:text-[12px]">{scene.narration_text}</p>

        {editing && (
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={4}
            className="w-full resize-none rounded-lg border border-white/[0.06] bg-white/[0.03] p-2.5 text-[11px] leading-relaxed text-white/80 placeholder:text-white/20 transition-all duration-300 focus:border-[#a855f7]/40 focus:bg-white/[0.05] focus:shadow-[0_0_0_4px_rgba(168,85,247,0.08)] sm:rounded-xl sm:p-3"
          />
        )}

        <div className="flex flex-wrap gap-2">
          {scene.image_prompt && (
            <button
              onClick={() => setEditing(!editing)}
              className="rounded-lg border border-white/[0.08] bg-white/[0.03] px-2.5 py-1.5 text-[10px] font-medium text-white/45 transition-all duration-200 hover:border-white/15 hover:bg-white/[0.06] hover:text-white/60 active:scale-[0.97] sm:rounded-xl sm:px-3 sm:py-2 sm:text-[11px]"
            >
              {editing ? "Cancelar" : "Editar prompt"}
            </button>
          )}
          {scene.image_prompt && (
            <button
              onClick={() => regenMutation.mutate()}
              disabled={regenMutation.isPending}
              className="btn-gradient rounded-lg px-2.5 py-1.5 text-[10px] font-semibold text-white disabled:opacity-30 sm:rounded-xl sm:px-3 sm:py-2 sm:text-[11px]"
            >
              {regenMutation.isPending ? (
                <span className="flex items-center gap-1.5">
                  <svg className="h-3 w-3 animate-spin" viewBox="0 0 24 24" fill="none">
                    <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
                  </svg>
                  Gerando...
                </span>
              ) : (
                "Regenerar"
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Sources / segments (modo criativo) ──────────────────────────────

function scoreColor(score: number): string {
  if (score >= 7.5) return "text-[#30d158] bg-[--green-soft]";
  if (score >= 5) return "text-[#ff9f0a] bg-[--orange-soft]";
  return "text-[#ff453a] bg-[--red-soft]";
}

function SegmentCard({
  projectId,
  segment,
  usedInScene,
  onChanged,
}: {
  projectId: number;
  segment: SourceSegment;
  usedInScene: number | null;
  onChanged: () => void;
}) {
  const [playing, setPlaying] = useState(false);

  const toggleMutation = useMutation({
    mutationFn: () => api.updateSegment(projectId, segment.id, { enabled: !segment.enabled }),
    onSuccess: onChanged,
  });

  const hookPotential = Number(segment.meta?.hook_potential ?? 0);
  const isImage = segment.meta?.kind === "image";

  return (
    <div
      className={`glass group overflow-hidden rounded-xl transition-all duration-300 animate-scale-in sm:rounded-2xl ${
        segment.enabled ? "hover:border-white/10" : "opacity-40 grayscale"
      }`}
    >
      <div
        className="relative aspect-video cursor-pointer overflow-hidden bg-black/40"
        onClick={() => segment.preview_path && setPlaying(!playing)}
      >
        {playing && segment.preview_path ? (
          <video
            src={mediaUrl(segment.preview_path)}
            autoPlay
            loop
            muted={false}
            playsInline
            className="h-full w-full object-cover"
            onClick={(e) => e.stopPropagation()}
            controls
          />
        ) : segment.thumbnail_path ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={mediaUrl(segment.thumbnail_path)}
            alt={segment.description || `Trecho ${segment.index + 1}`}
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-[10px] text-white/20">
            Processando...
          </div>
        )}

        {!playing && segment.preview_path && (
          <div className="absolute inset-0 flex items-center justify-center opacity-0 transition-opacity group-hover:opacity-100">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-black/60 backdrop-blur-md">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="white">
                <polygon points="6 3 20 12 6 21 6 3" />
              </svg>
            </div>
          </div>
        )}

        <div className="absolute inset-x-0 top-0 flex items-start justify-between p-2">
          <span className={`rounded-md px-1.5 py-0.5 text-[10px] font-bold backdrop-blur-md sm:rounded-lg ${scoreColor(segment.score)}`}>
            {segment.score.toFixed(1)}
          </span>
          <div className="flex gap-1">
            {hookPotential >= 7 && (
              <span className="rounded-md bg-[#a855f7]/80 px-1.5 py-0.5 text-[9px] font-semibold text-white backdrop-blur-md">
                HOOK
              </span>
            )}
            {usedInScene != null && (
              <span className="rounded-md bg-[#30d158]/80 px-1.5 py-0.5 text-[9px] font-semibold text-white backdrop-blur-md">
                Cena {usedInScene + 1}
              </span>
            )}
          </div>
        </div>
        {!isImage && (
          <span className="absolute bottom-2 right-2 rounded-md bg-black/60 px-1.5 py-0.5 text-[9px] font-medium text-white/70 backdrop-blur-md">
            {segment.duration.toFixed(1)}s
          </span>
        )}
      </div>

      <div className="space-y-1.5 p-2.5 sm:p-3">
        {segment.description && (
          <p className="line-clamp-2 text-[11px] leading-snug text-white/60">{segment.description}</p>
        )}
        {segment.transcript && (
          <p className="line-clamp-2 text-[10px] italic leading-snug text-white/30">
            “{segment.transcript}”
          </p>
        )}
        {segment.tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {segment.tags.slice(0, 3).map((tag) => (
              <span key={tag} className="rounded bg-white/[0.06] px-1.5 py-0.5 text-[9px] text-white/35">
                {tag}
              </span>
            ))}
          </div>
        )}
        <button
          onClick={() => toggleMutation.mutate()}
          disabled={toggleMutation.isPending}
          className={`w-full rounded-lg px-2 py-1.5 text-[10px] font-semibold transition-all active:scale-[0.97] ${
            segment.enabled
              ? "bg-white/[0.05] text-white/40 hover:bg-[--red-soft] hover:text-[#ff453a]"
              : "bg-[--green-soft] text-[#30d158]"
          }`}
        >
          {segment.enabled ? "Não usar este trecho" : "Usar este trecho"}
        </button>
      </div>
    </div>
  );
}

function SourcesSection({
  project,
  onChanged,
}: {
  project: ProjectDetail;
  onChanged: () => void;
}) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [libraryOpen, setLibraryOpen] = useState(false);

  const uploadMutation = useMutation({
    mutationFn: async (files: File[]) => {
      setUploading(true);
      try {
        await api.uploadSources(project.id, files);
      } finally {
        setUploading(false);
      }
    },
    onSuccess: () => {
      onChanged();
      queryClient.invalidateQueries({ queryKey: ["library"] });
    },
  });

  const attachMutation = useMutation({
    mutationFn: (ids: number[]) => api.attachFromLibrary(project.id, ids),
    onSuccess: onChanged,
  });

  const deleteMutation = useMutation({
    mutationFn: (sourceId: number) => api.deleteSource(project.id, sourceId),
    onSuccess: onChanged,
  });

  const segmentUsedIn = useMemo(() => {
    const map = new Map<number, number>();
    for (const scene of project.scenes) {
      if (scene.source_segment_id != null) map.set(scene.source_segment_id, scene.index);
    }
    return map;
  }, [project.scenes]);

  const processing = project.sources.some(
    (s) => s.status === "uploaded" || s.status === "processing",
  );

  return (
    <section className="space-y-2.5 sm:space-y-3">
      <div className="flex items-center justify-between px-1">
        <div className="flex items-center gap-2">
          <h2 className="text-[10px] font-semibold uppercase tracking-widest text-white/25 sm:text-[11px]">
            Sua mídia
          </h2>
          {processing && (
            <span className="flex items-center gap-1.5 rounded-md bg-[--orange-soft] px-2 py-0.5 text-[9px] font-medium text-[#ff9f0a]">
              <span className="h-1.5 w-1.5 rounded-full bg-[#ff9f0a] animate-shimmer" />
              Analisando trechos...
            </span>
          )}
        </div>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="video/*,image/*"
          onChange={(e) => {
            if (e.target.files?.length) uploadMutation.mutate(Array.from(e.target.files));
            e.target.value = "";
          }}
          className="hidden"
        />
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setLibraryOpen(true)}
            disabled={attachMutation.isPending}
            className="text-[10px] font-medium text-white/40 transition-colors hover:text-white/70 disabled:opacity-40 sm:text-[11px]"
          >
            Biblioteca
          </button>
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="text-[10px] font-medium text-[#c084fc] transition-colors hover:text-[#d8b4fe] disabled:opacity-40 sm:text-[11px]"
          >
            {uploading ? "Enviando..." : "+ Adicionar mídia"}
          </button>
        </div>
      </div>

      {project.sources.length === 0 ? (
        <div className="glass flex flex-col items-center rounded-xl py-8 text-center sm:rounded-2xl">
          <p className="text-[12px] text-white/30">Nenhuma mídia enviada ainda.</p>
          <p className="mt-1 text-[11px] text-white/20">
            Envie vídeos ou fotos, ou reutilize da biblioteca.
          </p>
          <button
            type="button"
            onClick={() => setLibraryOpen(true)}
            className="mt-3 text-[11px] font-medium text-[#c084fc] hover:text-[#d8b4fe]"
          >
            Abrir biblioteca
          </button>
        </div>
      ) : (
        project.sources.map((source) => (
          <div key={source.id} className="space-y-2">
            <div className="flex items-center justify-between px-1">
              <div className="flex min-w-0 items-center gap-2">
                <span className="truncate text-[11px] font-medium text-white/45 sm:text-[12px]">
                  {source.filename}
                </span>
                <span className="shrink-0 text-[10px] text-white/20">
                  {source.kind === "video"
                    ? `${(source.duration ?? 0).toFixed(0)}s · ${source.segments.length} trechos`
                    : "imagem"}
                </span>
                {source.status === "failed" && (
                  <span className="shrink-0 rounded bg-[--red-soft] px-1.5 py-0.5 text-[9px] text-[#ff453a]">
                    falhou: {source.error?.slice(0, 60)}
                  </span>
                )}
                {(source.status === "uploaded" || source.status === "processing") && (
                  <span className="shrink-0 rounded bg-[--orange-soft] px-1.5 py-0.5 text-[9px] text-[#ff9f0a]">
                    analisando...
                  </span>
                )}
              </div>
              <button
                type="button"
                onClick={() => deleteMutation.mutate(source.id)}
                className="shrink-0 text-[10px] text-white/20 transition-colors hover:text-[#ff453a]"
              >
                Remover
              </button>
            </div>
            {source.segments.length > 0 && (
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
                {source.segments.map((segment) => (
                  <SegmentCard
                    key={segment.id}
                    projectId={project.id}
                    segment={segment}
                    usedInScene={segmentUsedIn.get(segment.id) ?? null}
                    onChanged={onChanged}
                  />
                ))}
              </div>
            )}
          </div>
        ))
      )}

      <LibraryPickerModal
        open={libraryOpen}
        onClose={() => setLibraryOpen(false)}
        onConfirm={async (ids) => {
          await attachMutation.mutateAsync(ids);
        }}
        confirmLabel="Adicionar ao projeto"
      />
    </section>
  );
}

function JoinSourcesSection({
  project,
  onChanged,
}: {
  project: ProjectDetail;
  onChanged: () => void;
}) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [libraryOpen, setLibraryOpen] = useState(false);

  const uploadMutation = useMutation({
    mutationFn: async (files: File[]) => {
      setUploading(true);
      try {
        await api.uploadSources(project.id, files);
      } finally {
        setUploading(false);
      }
    },
    onSuccess: () => {
      onChanged();
      queryClient.invalidateQueries({ queryKey: ["library"] });
    },
  });

  const attachMutation = useMutation({
    mutationFn: (ids: number[]) => api.attachFromLibrary(project.id, ids),
    onSuccess: onChanged,
  });

  const deleteMutation = useMutation({
    mutationFn: (sourceId: number) => api.deleteSource(project.id, sourceId),
    onSuccess: onChanged,
  });

  const videos = [...project.sources]
    .filter((s) => s.kind === "video")
    .sort((a, b) => a.id - b.id);
  const processing = videos.some(
    (s) => s.status === "uploaded" || s.status === "processing",
  );
  const canEdit = project.status === "draft";

  return (
    <section className="space-y-2.5 sm:space-y-3">
      <div className="flex items-center justify-between px-1">
        <div className="flex items-center gap-2">
          <h2 className="text-[10px] font-semibold uppercase tracking-widest text-white/25 sm:text-[11px]">
            Partes do vídeo
          </h2>
          <span className="rounded-md bg-white/[0.06] px-1.5 py-0.5 text-[9px] font-medium text-white/30">
            {videos.length}
          </span>
          {processing && (
            <span className="flex items-center gap-1.5 rounded-md bg-[--orange-soft] px-2 py-0.5 text-[9px] font-medium text-[#ff9f0a]">
              <span className="h-1.5 w-1.5 rounded-full bg-[#ff9f0a] animate-shimmer" />
              Processando...
            </span>
          )}
        </div>
        {canEdit && (
          <>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept="video/*"
              onChange={(e) => {
                if (e.target.files?.length) uploadMutation.mutate(Array.from(e.target.files));
                e.target.value = "";
              }}
              className="hidden"
            />
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setLibraryOpen(true)}
                disabled={attachMutation.isPending}
                className="text-[10px] font-medium text-white/40 transition-colors hover:text-white/70 disabled:opacity-40 sm:text-[11px]"
              >
                Biblioteca
              </button>
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                className="text-[10px] font-medium text-[#c084fc] transition-colors hover:text-[#d8b4fe] disabled:opacity-40 sm:text-[11px]"
              >
                {uploading ? "Enviando..." : "+ Adicionar vídeo"}
              </button>
            </div>
          </>
        )}
      </div>

      {videos.length === 0 ? (
        <div className="glass flex flex-col items-center rounded-xl py-8 text-center sm:rounded-2xl">
          <p className="text-[12px] text-white/30">Nenhum vídeo enviado ainda.</p>
          <p className="mt-1 text-[11px] text-white/20">
            Envie pelo menos 2 partes, na ordem do vídeo final.
          </p>
        </div>
      ) : (
        <div className="glass divide-y divide-white/[0.04] rounded-xl sm:rounded-2xl">
          {videos.map((source, index) => (
            <div key={source.id} className="flex items-center justify-between gap-3 px-4 py-3">
              <div className="flex min-w-0 items-center gap-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-white/[0.06] text-[11px] font-semibold text-white/40">
                  {index + 1}
                </span>
                <span className="truncate text-[12px] text-white/60">{source.filename}</span>
              </div>
              <div className="flex shrink-0 items-center gap-3">
                <span className="text-[11px] text-white/25">
                  {source.status === "ready"
                    ? `${(source.duration ?? 0).toFixed(0)}s`
                    : source.status === "failed"
                      ? `falhou: ${source.error?.slice(0, 40) ?? ""}`
                      : "processando..."}
                </span>
                {canEdit && (
                  <button
                    type="button"
                    onClick={() => deleteMutation.mutate(source.id)}
                    className="text-[10px] text-white/20 transition-colors hover:text-[#ff453a]"
                  >
                    Remover
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {canEdit && videos.length > 0 && videos.length < 2 && (
        <p className="px-1 text-[11px] text-[#ff9f0a]/80">
          Faltam {2 - videos.length} vídeo(s) para poder juntar.
        </p>
      )}

      <LibraryPickerModal
        open={libraryOpen}
        onClose={() => setLibraryOpen(false)}
        onConfirm={async (ids) => {
          await attachMutation.mutateAsync(ids);
        }}
        confirmLabel="Adicionar ao projeto"
      />
    </section>
  );
}

// ── Cortes automáticos (modo edit) ──────────────────────────────────

const CUT_REASONS: Record<string, { label: string; color: string; bar: string }> = {
  voice_command: { label: "comando de voz", color: "bg-[--purple-soft] text-[#bf5af2]", bar: "bg-[#bf5af2]/70" },
  retake: { label: "retake", color: "bg-[--orange-soft] text-[#ff9f0a]", bar: "bg-[#ff9f0a]/70" },
  silence: { label: "silêncio", color: "bg-white/[0.08] text-white/45", bar: "bg-white/25" },
  filler: { label: "hesitação", color: "bg-[--cyan-soft] text-[#64d2ff]", bar: "bg-[#64d2ff]/70" },
  manual: { label: "manual", color: "bg-white/[0.08] text-white/60", bar: "bg-white/40" },
  speech: { label: "fala", color: "bg-[--green-soft] text-[#30d158]", bar: "bg-[#30d158]/60" },
};

function fmtTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds - m * 60;
  return `${m}:${s.toFixed(1).padStart(4, "0")}`;
}

function EditCutCard({
  projectId,
  cut,
  locked,
  onChanged,
}: {
  projectId: number;
  cut: EditCut;
  locked: boolean;
  onChanged: () => void;
}) {
  const [playing, setPlaying] = useState(false);
  const isKeep = cut.action === "keep";
  const reason = CUT_REASONS[cut.reason] ?? CUT_REASONS.speech;

  const toggleMutation = useMutation({
    mutationFn: () => api.updateEditCut(projectId, cut.id, isKeep ? "cut" : "keep"),
    onSuccess: onChanged,
  });

  return (
    <div
      className={`glass group overflow-hidden rounded-xl transition-all duration-300 animate-scale-in sm:rounded-2xl ${
        isKeep ? "hover:border-white/10" : "opacity-55 grayscale-[0.4]"
      }`}
    >
      <div
        className="relative aspect-video cursor-pointer overflow-hidden bg-black/40"
        onClick={() => cut.preview_path && setPlaying(!playing)}
      >
        {playing && cut.preview_path ? (
          <video
            src={mediaUrl(cut.preview_path)}
            autoPlay
            loop
            playsInline
            controls
            className="h-full w-full object-cover"
            onClick={(e) => e.stopPropagation()}
          />
        ) : cut.thumbnail_path ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={mediaUrl(cut.thumbnail_path)}
            alt={`Trecho ${cut.index + 1}`}
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-[10px] text-white/20">
            Sem prévia
          </div>
        )}

        {!playing && cut.preview_path && (
          <div className="absolute inset-0 flex items-center justify-center opacity-0 transition-opacity group-hover:opacity-100">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-black/60 backdrop-blur-md">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="white">
                <polygon points="6 3 20 12 6 21 6 3" />
              </svg>
            </div>
          </div>
        )}

        <div className="absolute inset-x-0 top-0 flex items-start justify-between p-2">
          <span
            className={`rounded-md px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide backdrop-blur-md sm:rounded-lg ${
              isKeep ? "bg-[#30d158]/85 text-white" : "bg-[#ff453a]/85 text-white"
            }`}
          >
            {isKeep ? "mantido" : "cortado"}
          </span>
          <span className={`rounded-md px-1.5 py-0.5 text-[9px] font-medium backdrop-blur-md ${reason.color}`}>
            {reason.label}
          </span>
        </div>
        <span className="absolute bottom-2 right-2 rounded-md bg-black/60 px-1.5 py-0.5 text-[9px] font-medium text-white/70 backdrop-blur-md">
          {fmtTime(cut.start)} – {fmtTime(cut.end)} · {cut.duration.toFixed(1)}s
        </span>
      </div>

      <div className="space-y-1.5 p-2.5 sm:p-3">
        {cut.detail && (
          <p className="line-clamp-2 text-[10px] leading-snug text-white/40">{cut.detail}</p>
        )}
        {cut.transcript && (
          <p className="line-clamp-2 text-[10px] italic leading-snug text-white/30">
            “{cut.transcript}”
          </p>
        )}
        {!locked && (
          <button
            onClick={() => toggleMutation.mutate()}
            disabled={toggleMutation.isPending}
            className={`w-full rounded-lg px-2 py-1.5 text-[10px] font-semibold transition-all active:scale-[0.97] ${
              isKeep
                ? "bg-white/[0.05] text-white/40 hover:bg-[--red-soft] hover:text-[#ff453a]"
                : "bg-[--green-soft] text-[#30d158]"
            }`}
          >
            {isKeep ? "Cortar este trecho" : "Manter este trecho"}
          </button>
        )}
      </div>
    </div>
  );
}

function EditCutsSection({
  project,
  onChanged,
}: {
  project: ProjectDetail;
  onChanged: () => void;
}) {
  const [onlyCuts, setOnlyCuts] = useState(false);
  const cuts = [...(project.edit_cuts ?? [])].sort((a, b) => a.start - b.start);
  if (cuts.length === 0) return null;

  const total = cuts[cuts.length - 1].end;
  const kept = cuts.filter((c) => c.action === "keep").reduce((s, c) => s + c.duration, 0);
  const removed = total - kept;
  const nCuts = cuts.filter((c) => c.action === "cut").length;
  const locked = isActive(project.status);
  const visible = onlyCuts ? cuts.filter((c) => c.action === "cut" || c.reason === "manual") : cuts;

  return (
    <section className="space-y-2.5 sm:space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 px-1">
        <div className="flex items-center gap-2">
          <h2 className="text-[10px] font-semibold uppercase tracking-widest text-white/25 sm:text-[11px]">
            Cortes sugeridos
          </h2>
          <span className="rounded-md bg-white/[0.06] px-1.5 py-0.5 text-[9px] font-medium text-white/30 sm:px-2 sm:text-[10px]">
            {nCuts} cortes · −{removed.toFixed(0)}s · final ~{fmtTime(kept)}
          </span>
        </div>
        <button
          onClick={() => setOnlyCuts(!onlyCuts)}
          className="text-[10px] font-medium text-white/25 transition-colors hover:text-white/45 sm:text-[11px]"
        >
          {onlyCuts ? "Ver todos os trechos" : "Ver só os cortes"}
        </button>
      </div>

      {/* Timeline proporcional do vídeo */}
      <div className="glass rounded-xl p-3 sm:rounded-2xl sm:p-4">
        <div className="flex h-6 w-full overflow-hidden rounded-lg bg-black/40 sm:h-7">
          {cuts.map((cut) => {
            const reason = CUT_REASONS[cut.reason] ?? CUT_REASONS.speech;
            const width = (cut.duration / Math.max(total, 0.1)) * 100;
            return (
              <div
                key={cut.id}
                title={`${fmtTime(cut.start)}–${fmtTime(cut.end)} · ${
                  cut.action === "keep" ? "mantido" : `cortado (${reason.label})`
                }`}
                style={{ width: `${width}%` }}
                className={`h-full border-r border-black/40 transition-opacity ${
                  cut.action === "keep" ? "bg-[#30d158]/60" : reason.bar
                } ${cut.action === "cut" ? "opacity-50" : ""}`}
              />
            );
          })}
        </div>
        <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
          {["speech", "voice_command", "retake", "silence", "filler"].map((key) => (
            <span key={key} className="flex items-center gap-1.5 text-[9px] text-white/30">
              <span className={`h-2 w-2 rounded-sm ${key === "speech" ? "bg-[#30d158]/60" : `${CUT_REASONS[key].bar} opacity-50`}`} />
              {key === "speech" ? "mantido" : CUT_REASONS[key].label}
            </span>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
        {visible.map((cut) => (
          <EditCutCard
            key={cut.id}
            projectId={project.id}
            cut={cut}
            locked={locked}
            onChanged={onChanged}
          />
        ))}
      </div>
    </section>
  );
}

// ── Hooks alternativos (modo criativo) ──────────────────────────────

function AlternativeHooks({ asset }: { asset: Asset }) {
  const hooks = (asset.meta?.alternative_hooks as string[] | undefined) ?? [];
  const angle = asset.meta?.angle as string | undefined;
  if (hooks.length === 0) return null;
  return (
    <section className="space-y-2.5 sm:space-y-3">
      <div className="flex items-center gap-2 px-1">
        <h2 className="text-[10px] font-semibold uppercase tracking-widest text-white/25 sm:text-[11px]">
          Hooks alternativos para teste A/B
        </h2>
        {angle && (
          <span className="rounded-md bg-[--accent-soft] px-2 py-0.5 text-[9px] font-medium text-[#c084fc]">
            ângulo: {angle}
          </span>
        )}
      </div>
      <div className="glass space-y-2 rounded-xl p-4 sm:rounded-2xl sm:p-5">
        <p className="text-[11px] leading-relaxed text-white/30">
          O hook responde pela maior parte da performance do criativo. Teste variações
          trocando só os 3 primeiros segundos:
        </p>
        {hooks.map((hook, i) => (
          <div key={i} className="flex items-start gap-2.5 rounded-lg bg-white/[0.03] px-3 py-2.5">
            <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded bg-[--accent-soft] text-[9px] font-bold text-[#c084fc]">
              {i + 1}
            </span>
            <p className="text-[12px] leading-relaxed text-white/70">{hook}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

// ── Publish meta ─────────────────────────────────────────────────────

interface PlatformMeta {
  platform: string;
  title: string;
  description: string;
  hashtags: string[];
  keywords: string[];
  category: string;
}

const PLATFORM_ICONS: Record<string, { gradient: string; label: string }> = {
  tiktok: { gradient: "from-[#ff0050] to-[#00f2ea]", label: "TikTok" },
  reels: { gradient: "from-[#f58529] to-[#dd2a7b]", label: "Reels" },
  shorts: { gradient: "from-[#ff0000] to-[#cc0000]", label: "Shorts" },
};

function PublishMetaSection({ asset }: { asset: Asset }) {
  const { data: meta } = useQuery({
    queryKey: ["publish_meta", asset.id],
    queryFn: () =>
      fetch(mediaUrl(asset.path))
        .then((r) => r.json() as Promise<{ platforms: PlatformMeta[] }>),
    staleTime: Infinity,
  });

  if (!meta) return null;
  return (
    <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3">
      {meta.platforms.map((p) => {
        const platform = PLATFORM_ICONS[p.platform.toLowerCase()] ?? {
          gradient: "from-white/20 to-white/10",
          label: p.platform,
        };
        return (
          <div key={p.platform} className="glass rounded-xl p-4 space-y-2.5 animate-scale-in sm:rounded-2xl sm:p-5 sm:space-y-3">
            <div className="flex items-center gap-2.5">
              <div className={`h-7 w-7 shrink-0 rounded-lg bg-gradient-to-br ${platform.gradient} flex items-center justify-center`}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="white" className="opacity-90">
                  <polygon points="5 3 19 12 5 21 5 3" />
                </svg>
              </div>
              <span className="text-[11px] font-semibold uppercase tracking-wider text-white/50 sm:text-[12px]">
                {platform.label}
              </span>
            </div>
            <p className="text-[13px] font-medium leading-snug text-white/85 sm:text-[14px]">{p.title}</p>
            <p className="whitespace-pre-line text-[11px] leading-relaxed text-white/40 sm:text-[12px]">{p.description}</p>
            <div className="flex flex-wrap gap-1.5">
              {p.hashtags.map((h) => (
                <span key={h} className="rounded-md bg-[--accent-soft] px-1.5 py-0.5 text-[9px] font-medium text-[#c084fc] sm:px-2 sm:text-[10px]">
                  #{h}
                </span>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Instagram Publish Section ────────────────────────────────────────

function InstagramPublishSection({ project }: { project: ProjectDetail }) {
  const queryClient = useQueryClient();

  const { data: igStatus } = useQuery({
    queryKey: ["instagram_status", project.workspace_id],
    queryFn: () => project.workspace_id ? api.getInstagramStatus(project.workspace_id) : Promise.resolve({ connected: false } as InstagramStatus),
    enabled: !!project.workspace_id,
    staleTime: 30_000,
  });

  const { data: publications } = useQuery({
    queryKey: ["publications", project.id],
    queryFn: () => api.listPublications({ projectId: project.id }),
    refetchInterval: (query) => shouldPollPublications(query.state.data),
  });

  const publishMutation = useMutation({
    mutationFn: () => api.publishToInstagram(project.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["publications", project.id] });
    },
  });

  const disconnectMutation = useMutation({
    mutationFn: () => api.disconnectInstagram(project.workspace_id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["instagram_status", project.workspace_id] });
    },
  });

  if (!project.workspace_id) {
    return (
      <div className="glass rounded-xl p-4 sm:rounded-2xl sm:p-5">
        <p className="text-[12px] text-white/40">
          Associe este projeto a um workspace para conectar o Instagram.
        </p>
      </div>
    );
  }

  const hasVideo = project.assets.some((a) => a.kind === "video" && a.is_current);
  const latestPub = publications?.[0];
  const isPublished = publications?.some((p) => p.status === "published") ?? false;
  const isPublishing = latestPub?.status === "uploading" || publishMutation.isPending;

  return (
    <div className="glass rounded-xl p-4 space-y-4 sm:rounded-2xl sm:p-5">
      {/* Conta conectada ou botão de conectar */}
      {igStatus?.connected ? (
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {igStatus.profile_picture_url && (
              <img
                src={igStatus.profile_picture_url}
                alt=""
                className="h-8 w-8 rounded-full ring-2 ring-[#c084fc]/30"
              />
            )}
            <div>
              <p className="text-[13px] font-medium text-white/80">{igStatus.name}</p>
              <p className="text-[10px] text-white/30">Instagram conectado</p>
            </div>
            <span className="inline-flex items-center gap-1 rounded-full bg-green-500/20 px-2 py-0.5 text-[10px] font-medium text-green-400">
              <span className="h-1.5 w-1.5 rounded-full bg-green-400" />
              Ativo
            </span>
          </div>
          <button
            onClick={() => disconnectMutation.mutate()}
            className="rounded-lg px-2.5 py-1 text-[11px] text-white/30 transition hover:bg-white/[0.06] hover:text-red-400"
          >
            Desconectar
          </button>
        </div>
      ) : (
        <a
          href={instagramConnectUrl(project.workspace_id)}
          className="flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-[#f58529] via-[#dd2a7b] to-[#8134af] px-4 py-2.5 text-[13px] font-semibold text-white transition hover:opacity-90"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="white">
            <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z"/>
          </svg>
          Conectar Instagram
        </a>
      )}

      {/* Botão de publicar — escondido se já publicado */}
      {igStatus?.connected && hasVideo && !isPublished && (
        <div className="space-y-3">
          <button
            onClick={() => publishMutation.mutate()}
            disabled={isPublishing}
            className="w-full rounded-xl bg-gradient-to-r from-[#f58529] via-[#dd2a7b] to-[#8134af] px-4 py-2.5 text-[13px] font-semibold text-white transition hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isPublishing ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                  <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
                </svg>
                Publicando...
              </span>
            ) : (
              "🚀 Publicar como Reel"
            )}
          </button>

          {publishMutation.isError && (
            <p className="text-[11px] text-red-400">
              Erro: {(publishMutation.error as Error)?.message ?? "Falha ao publicar"}
            </p>
          )}
        </div>
      )}

      {/* Status de publicações recentes + Insights */}
      {publications && publications.length > 0 && (
        <div className="space-y-3 border-t border-white/[0.06] pt-3">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-white/25">
            Publicações
          </p>
          {publications.slice(0, 3).map((pub) => (
            <div key={pub.id} className="space-y-3">
              <div className="flex items-center justify-between rounded-lg bg-white/[0.03] px-3 py-2">
                <div className="flex items-center gap-2">
                  <span className={`h-2 w-2 rounded-full ${
                    pub.status === "published" ? "bg-green-400" :
                    pub.status === "failed" ? "bg-red-400" :
                    "bg-yellow-400 animate-pulse"
                  }`} />
                  <span className="text-[12px] text-white/60">
                    {pub.status === "published" ? "Publicado" :
                     pub.status === "failed" ? "Falhou" :
                     pub.status === "uploading" ? "Enviando..." :
                     "Agendado"}
                  </span>
                </div>
                {pub.status === "failed" && pub.error && (
                  <span className="max-w-[200px] truncate text-[10px] text-red-400/70" title={pub.error}>
                    {pub.error}
                  </span>
                )}
              </div>

              {/* Insights da publicação */}
              {pub.status === "published" && pub.external_id && (
                <InsightsPanel pubId={pub.id} />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Project detail page ──────────────────────────────────────────────

export default function ProjectPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const projectId = Number(id);
  const queryClient = useQueryClient();
  const [showLogs, setShowLogs] = useState(false);

  const projectQuery = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => api.getProject(projectId),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 4_000;
      const sourcesProcessing = data.sources?.some(
        (s) => s.status === "uploaded" || s.status === "processing",
      );
      return isActive(data.status) || data.status === "awaiting_review" || sourcesProcessing
        ? 4_000
        : false;
    },
  });

  const stagesQuery = useQuery({
    queryKey: ["stages", projectId],
    queryFn: () => api.getStages(projectId),
    refetchInterval: () => {
      const project = projectQuery.data;
      if (!project) return 4_000;
      return isActive(project.status) || project.status === "awaiting_review" ? 4_000 : false;
    },
    enabled: projectQuery.isSuccess,
  });

  const invalidateProject = () => {
    queryClient.invalidateQueries({ queryKey: ["project", projectId] });
    queryClient.invalidateQueries({ queryKey: ["stages", projectId] });
    queryClient.invalidateQueries({ queryKey: ["projects"] });
  };

  const approveMutation = useMutation({
    mutationFn: () => api.approve(projectId),
    onSuccess: invalidateProject,
  });

  const rejectMutation = useMutation({
    mutationFn: () => api.reject(projectId),
    onSuccess: invalidateProject,
  });

  const runMutation = useMutation({
    mutationFn: (fromStage?: string) => api.runProject(projectId, fromStage),
    onSuccess: invalidateProject,
  });

  const project = projectQuery.data;
  const stages = stagesQuery.data ?? [];
  const error = projectQuery.error ?? stagesQuery.error;

  if (!project) {
    return (
      <div className="mx-auto flex max-w-[980px] items-center justify-center px-4 py-24 sm:px-6 sm:py-32">
        {error instanceof Error ? (
          <div className="flex items-center gap-2 px-4 text-[13px] text-[#ff453a] sm:text-[14px]">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0">
              <circle cx="12" cy="12" r="10" /><path d="M12 8v4M12 16h.01" />
            </svg>
            {error.message}
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <svg className="h-6 w-6 animate-spin text-white/20" viewBox="0 0 24 24" fill="none">
              <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
            </svg>
            <span className="text-[13px] text-white/25">Carregando...</span>
          </div>
        )}
      </div>
    );
  }

  const currentAssets = project.assets.filter((a) => a.is_current);
  const video = currentAssets.find((a) => a.kind === "video");
  const publishMeta = currentAssets.find((a) => a.kind === "publish_meta");
  const scriptAsset = currentAssets.find((a) => a.kind === "script");
  const imageByScene = new Map(
    currentAssets
      .filter((a) => a.kind === "image" && a.scene_id != null)
      .map((a) => [a.scene_id, a]),
  );
  const failedRun = stages.find((s) => s.status === "failed");
  const awaiting = project.status === "awaiting_review";
  const segmentThumbById = new Map<number, string | null>();
  for (const source of project.sources ?? []) {
    for (const segment of source.segments) {
      segmentThumbById.set(segment.id, segment.thumbnail_path);
    }
  }
  const isCreative = project.mode === "creative";
  const isEdit = project.mode === "edit";
  const isJoin = project.mode === "join";
  const order = stageOrder(project.mode);
  const labels = stageLabels(project.mode);
  const sourcesProcessing = (project.sources ?? []).some(
    (s) => s.status === "uploaded" || s.status === "processing",
  );
  const joinVideoCount = (project.sources ?? []).filter((s) => s.kind === "video").length;
  const hasRun = stages.length > 0;

  return (
    <div className="mx-auto max-w-[980px] space-y-6 px-4 pb-16 pt-2 animate-slide-up sm:space-y-8 sm:px-6">
      {/* ── Header ──────────────────────────────────────────── */}
      <div>
        <Link
          href={project.workspace_id ? `/workspaces/${project.workspace_id}` : "/workspaces"}
          className="inline-flex items-center gap-1 text-[11px] font-medium text-white/30 transition-colors hover:text-white/50 sm:gap-1.5 sm:text-[12px]"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
          Voltar ao projeto
        </Link>

        <div className="mt-3 sm:mt-4">
          <h1 className="text-[22px] font-semibold tracking-tight leading-tight sm:text-[28px]">
            {project.title ?? project.topic}
          </h1>
          <p className="mt-1.5 text-[13px] leading-relaxed text-white/35 sm:mt-2 sm:max-w-2xl sm:text-[14px]">
            {project.topic}
          </p>

          {/* Action buttons - full width on mobile, inline on desktop */}
          <div className="mt-4 flex flex-wrap gap-2 sm:mt-5">
            {awaiting && (
              <>
                <button
                  onClick={() => approveMutation.mutate()}
                  disabled={approveMutation.isPending}
                  className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-[#30d158] px-4 py-2.5 text-[13px] font-semibold text-white shadow-lg shadow-[#30d158]/20 transition-all duration-200 hover:bg-[#34d65c] active:scale-[0.97] disabled:opacity-30 sm:flex-none sm:px-5"
                >
                  <IconCheck />
                  {isEdit ? "Aprovar cortes e renderizar" : "Aprovar"}
                </button>
                <button
                  onClick={() => rejectMutation.mutate()}
                  disabled={rejectMutation.isPending}
                  className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-[#ff453a]/90 px-4 py-2.5 text-[13px] font-semibold text-white shadow-lg shadow-[#ff453a]/20 transition-all duration-200 hover:bg-[#ff453a] active:scale-[0.97] disabled:opacity-30 sm:flex-none sm:px-5"
                >
                  <IconX />
                  Rejeitar
                </button>
              </>
            )}
            {(isCreative || isEdit || isJoin) && project.status === "draft" && (
              <button
                onClick={() => runMutation.mutate(undefined)}
                disabled={
                  runMutation.isPending ||
                  sourcesProcessing ||
                  (isJoin && joinVideoCount < 2)
                }
                className="btn-gradient w-full rounded-xl px-5 py-2.5 text-[13px] font-semibold text-white shadow-lg shadow-[#a855f7]/20 disabled:opacity-30 disabled:shadow-none sm:w-auto sm:px-6"
              >
                {sourcesProcessing
                  ? "Aguardando análise da mídia..."
                  : runMutation.isPending
                    ? "Iniciando..."
                    : isEdit
                      ? "Analisar e cortar"
                      : isJoin
                        ? "Juntar vídeos"
                        : "Gerar criativo"}
              </button>
            )}
            {!isActive(project.status) &&
              project.status !== "awaiting_review" &&
              !((isCreative || isEdit || isJoin) && project.status === "draft") && (
              <button
                onClick={() => runMutation.mutate(failedRun?.stage)}
                disabled={runMutation.isPending}
                className="w-full rounded-xl border border-white/[0.08] bg-white/[0.03] px-4 py-2.5 text-[13px] font-medium text-white/60 transition-all duration-200 hover:border-[#a855f7]/30 hover:bg-[--accent-soft] hover:text-[#c084fc] active:scale-[0.97] disabled:opacity-30 sm:w-auto sm:px-5"
              >
                {project.status === "failed" || project.error ? "Tentar novamente" : "Reprocessar"}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* ── Pipeline ────────────────────────────────────────── */}
      <section className="space-y-2.5 sm:space-y-3">
        <div className="flex items-center justify-between px-1">
          <h2 className="text-[10px] font-semibold uppercase tracking-widest text-white/25 sm:text-[11px]">
            Pipeline
          </h2>
          <button
            onClick={() => setShowLogs(!showLogs)}
            className="text-[10px] font-medium text-white/25 transition-colors hover:text-white/45 sm:text-[11px]"
          >
            {showLogs ? "Ocultar logs" : "Ver logs"}
          </button>
        </div>
        <PipelineProgress stages={stages} labels={labels} order={order} />
        {project.error && (
          <div className="flex items-start gap-2 rounded-lg bg-[--red-soft] px-3 py-2.5 text-[12px] text-[#ff453a] sm:items-center sm:rounded-xl sm:px-4 sm:py-3 sm:text-[13px]">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mt-0.5 shrink-0 sm:mt-0">
              <circle cx="12" cy="12" r="10" /><path d="M12 8v4M12 16h.01" />
            </svg>
            {project.error}
          </div>
        )}
        {showLogs && (
          <pre className="glass max-h-60 overflow-auto rounded-xl p-3.5 text-[10px] leading-relaxed text-white/40 font-mono animate-scale-in sm:max-h-72 sm:rounded-2xl sm:p-5 sm:text-[11px]">
            {stages
              .map(
                (s) =>
                  `── ${labels[s.stage]} (${s.status})\n${s.log}${s.error ? `ERRO: ${s.error}\n` : ""}`,
              )
              .join("\n")}
          </pre>
        )}
      </section>

      {/* ── Mídia enviada (modo criativo) ───────────────────── */}
      {isCreative && <SourcesSection project={project} onChanged={invalidateProject} />}

      {/* ── Partes para juntar (modo join) ───────────────────── */}
      {isJoin && <JoinSourcesSection project={project} onChanged={invalidateProject} />}

      {/* ── Cortes sugeridos (modo edit) ────────────────────── */}
      {isEdit && <EditCutsSection project={project} onChanged={invalidateProject} />}

      {/* ── Vídeo bruto (modo edit, antes da análise) ───────── */}
      {isEdit && (project.edit_cuts ?? []).length === 0 && project.sources.length > 0 && (
        <section className="space-y-2.5 sm:space-y-3">
          <h2 className="px-1 text-[10px] font-semibold uppercase tracking-widest text-white/25 sm:text-[11px]">
            Vídeo bruto
          </h2>
          <div className="glass rounded-xl p-4 sm:rounded-2xl">
            {project.sources.map((source) => (
              <div key={source.id} className="flex items-center justify-between gap-3">
                <span className="truncate text-[12px] text-white/60">{source.filename}</span>
                <span className="shrink-0 text-[11px] text-white/25">
                  {source.status === "ready"
                    ? `${(source.duration ?? 0).toFixed(0)}s`
                    : source.status === "failed"
                      ? `falhou: ${source.error?.slice(0, 50)}`
                      : "processando..."}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Video ───────────────────────────────────────────── */}
      {video && (
        <section className="space-y-2.5 sm:space-y-3">
          <h2 className="px-1 text-[10px] font-semibold uppercase tracking-widest text-white/25 sm:text-[11px]">
            Vídeo final
          </h2>
          <div className="glass flex justify-center rounded-2xl p-3 sm:rounded-3xl sm:p-8">
            <div className="relative w-full overflow-hidden rounded-xl shadow-2xl shadow-black/40 sm:w-auto sm:rounded-2xl">
              <video
                key={video.id}
                src={mediaUrl(video.path)}
                controls
                playsInline
                className="w-full rounded-xl sm:max-h-[70vh] sm:w-auto sm:rounded-2xl"
              />
            </div>
          </div>
        </section>
      )}

      {/* ── Hooks alternativos (modo criativo) ──────────────── */}
      {isCreative && scriptAsset && <AlternativeHooks asset={scriptAsset} />}

      {/* ── Scenes ──────────────────────────────────────────── */}
      {project.scenes.length > 0 && (
        <section className="space-y-2.5 sm:space-y-3">
          <div className="flex items-center gap-2 px-1">
            <h2 className="text-[10px] font-semibold uppercase tracking-widest text-white/25 sm:text-[11px]">
              Cenas
            </h2>
            <span className="rounded-md bg-white/[0.06] px-1.5 py-0.5 text-[9px] font-medium text-white/30 sm:px-2 sm:text-[10px]">
              {project.scenes.length}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2.5 sm:gap-3 md:grid-cols-3 lg:grid-cols-4">
            {project.scenes.map((scene, i) => (
              <div key={scene.id} style={{ animationDelay: `${i * 60}ms` }}>
                <SceneCard
                  project={project}
                  scene={scene}
                  image={imageByScene.get(scene.id)}
                  segmentThumb={
                    scene.source_segment_id != null
                      ? segmentThumbById.get(scene.source_segment_id) ?? null
                      : null
                  }
                  onChanged={invalidateProject}
                />
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Publish Meta ────────────────────────────────────── */}
      {publishMeta && (
        <section className="space-y-2.5 sm:space-y-3">
          <h2 className="px-1 text-[10px] font-semibold uppercase tracking-widest text-white/25 sm:text-[11px]">
            Metadados de publicação
          </h2>
          <PublishMetaSection asset={publishMeta} />
        </section>
      )}

      {/* ── Instagram Publish & Insights ─────────────────── */}
      {video && (
        <section className="space-y-2.5 sm:space-y-3">
          <h2 className="px-1 text-[10px] font-semibold uppercase tracking-widest text-white/25 sm:text-[11px]">
            Instagram
          </h2>
          <InstagramPublishSection project={project} />
        </section>
      )}
    </div>
  );
}
