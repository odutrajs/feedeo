"use client";

import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, LibraryAsset, mediaUrl } from "@/lib/api";

function formatDuration(seconds: number | null): string {
  if (seconds == null || !Number.isFinite(seconds)) return "";
  const s = Math.round(seconds);
  const m = Math.floor(s / 60);
  const r = s % 60;
  return m > 0 ? `${m}:${String(r).padStart(2, "0")}` : `${r}s`;
}

export function LibraryPickerModal({
  open,
  onClose,
  onConfirm,
  confirmLabel = "Usar selecionados",
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: (ids: number[]) => void | Promise<void>;
  confirmLabel?: string;
}) {
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);

  const { data: items = [], isLoading } = useQuery({
    queryKey: ["library"],
    queryFn: api.listLibrary,
    enabled: open,
  });

  if (!open) return null;

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleConfirm() {
    if (selected.size === 0) return;
    setBusy(true);
    try {
      await onConfirm(Array.from(selected));
      setSelected(new Set());
      onClose();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-end justify-center sm:items-center">
      <button
        type="button"
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
        aria-label="Fechar"
      />
      <div className="relative z-10 flex max-h-[85dvh] w-full max-w-lg flex-col rounded-t-2xl border border-white/[0.08] bg-[#121216] shadow-2xl sm:rounded-2xl">
        <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-3.5 sm:px-5">
          <div>
            <h3 className="text-[14px] font-semibold text-white/90">Biblioteca</h3>
            <p className="text-[11px] text-white/35">
              Escolha mídias já enviadas — sem precisar subir de novo.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-2 py-1 text-[12px] text-white/40 hover:text-white/70"
          >
            Fechar
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-3 sm:p-4">
          {isLoading ? (
            <p className="py-10 text-center text-[12px] text-white/30">Carregando...</p>
          ) : items.length === 0 ? (
            <div className="py-10 text-center">
              <p className="text-[12px] text-white/35">Sua biblioteca está vazia.</p>
              <p className="mt-1 text-[11px] text-white/20">
                Ao enviar mídia em um criativo, ela fica salva aqui automaticamente.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {items.map((item) => {
                const isOn = selected.has(item.id);
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => toggle(item.id)}
                    className={`group relative overflow-hidden rounded-xl border text-left transition-all ${
                      isOn
                        ? "border-[#a855f7]/60 bg-[#a855f7]/10 ring-1 ring-[#a855f7]/40"
                        : "border-white/[0.06] bg-white/[0.03] hover:border-white/[0.12]"
                    }`}
                  >
                    <div className="aspect-[9/12] bg-black/40">
                      {item.thumbnail_path ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={mediaUrl(item.thumbnail_path)}
                          alt=""
                          className="h-full w-full object-cover"
                        />
                      ) : (
                        <div className="flex h-full items-center justify-center text-white/20">
                          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                            <rect x="2" y="2" width="20" height="20" rx="4" />
                            <path d="M10 9l5 3-5 3V9z" />
                          </svg>
                        </div>
                      )}
                    </div>
                    <div className="space-y-0.5 p-2">
                      <p className="truncate text-[11px] font-medium text-white/70">{item.filename}</p>
                      <p className="text-[10px] text-white/30">
                        {item.kind === "video"
                          ? formatDuration(item.duration) || "vídeo"
                          : "imagem"}
                      </p>
                    </div>
                    {isOn && (
                      <span className="absolute right-1.5 top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-[#a855f7] text-[10px] font-bold text-white">
                        ✓
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-white/[0.06] px-4 py-3 sm:px-5">
          <span className="text-[11px] text-white/30">
            {selected.size === 0
              ? "Nenhum selecionado"
              : `${selected.size} selecionado${selected.size > 1 ? "s" : ""}`}
          </span>
          <button
            type="button"
            disabled={selected.size === 0 || busy}
            onClick={handleConfirm}
            className="btn-gradient rounded-xl px-4 py-2 text-[12px] font-semibold text-white disabled:opacity-30"
          >
            {busy ? "Adicionando..." : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

/** Grade da biblioteca no dashboard (gerenciar / excluir). */
export function LibrarySection() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  const { data: items = [] } = useQuery({
    queryKey: ["library"],
    queryFn: api.listLibrary,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteLibraryAsset(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["library"] }),
  });

  const uploadMutation = useMutation({
    mutationFn: async (files: File[]) => {
      setUploading(true);
      try {
        await api.uploadToLibrary(files);
      } finally {
        setUploading(false);
      }
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["library"] }),
  });

  const label = useMemo(
    () => (items.length === 1 ? "1 arquivo" : `${items.length} arquivos`),
    [items.length],
  );

  return (
    <section className="space-y-3 sm:space-y-4">
      <div className="flex items-center justify-between px-1">
        <div>
          <h2 className="text-[12px] font-semibold uppercase tracking-widest text-white/30 sm:text-[13px]">
            Biblioteca
          </h2>
          <p className="mt-0.5 text-[11px] text-white/25">
            Mídias salvas para reusar em novos criativos
          </p>
        </div>
        <div className="flex items-center gap-3">
          {items.length > 0 && (
            <span className="text-[11px] text-white/25 sm:text-[12px]">{label}</span>
          )}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept="video/*,image/*"
            className="hidden"
            onChange={(e) => {
              if (e.target.files?.length) uploadMutation.mutate(Array.from(e.target.files));
              e.target.value = "";
            }}
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="text-[11px] font-medium text-[#c084fc] hover:text-[#d8b4fe] disabled:opacity-40"
          >
            {uploading ? "Enviando..." : "+ Enviar"}
          </button>
        </div>
      </div>

      {items.length === 0 ? (
        <div className="glass flex flex-col items-center rounded-2xl py-10 text-center sm:rounded-3xl">
          <p className="text-[12px] text-white/30">Nenhuma mídia na biblioteca ainda.</p>
          <p className="mt-1 max-w-sm text-[11px] text-white/20">
            Todo upload em um criativo fica salvo aqui. Você também pode enviar direto.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
          {items.map((item: LibraryAsset) => (
            <div
              key={item.id}
              className="group relative overflow-hidden rounded-xl border border-white/[0.06] bg-white/[0.03]"
            >
              <div className="aspect-[9/12] bg-black/40">
                {item.thumbnail_path ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={mediaUrl(item.thumbnail_path)}
                    alt=""
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="flex h-full items-center justify-center text-white/20">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <rect x="2" y="2" width="20" height="20" rx="4" />
                      <path d="M10 9l5 3-5 3V9z" />
                    </svg>
                  </div>
                )}
              </div>
              <div className="space-y-0.5 p-2.5">
                <p className="truncate text-[11px] font-medium text-white/65">{item.filename}</p>
                <p className="text-[10px] text-white/30">
                  {item.kind === "video" ? formatDuration(item.duration) || "vídeo" : "imagem"}
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  if (confirm(`Remover "${item.filename}" da biblioteca?`)) {
                    deleteMutation.mutate(item.id);
                  }
                }}
                className="absolute right-1.5 top-1.5 rounded-md bg-black/60 px-1.5 py-0.5 text-[10px] text-white/50 opacity-0 transition-opacity hover:text-[#ff453a] group-hover:opacity-100"
              >
                Remover
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
