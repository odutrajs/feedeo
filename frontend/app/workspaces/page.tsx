"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export default function WorkspacesPage() {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const { data: workspaces = [], error } = useQuery({
    queryKey: ["workspaces"],
    queryFn: api.listWorkspaces,
  });

  const createMutation = useMutation({
    mutationFn: () => api.createWorkspace({ name: name.trim(), description: description.trim() }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workspaces"] });
      setName("");
      setDescription("");
      setCreating(false);
    },
  });

  return (
    <div className="mx-auto max-w-[980px] space-y-8 px-4 pb-16 pt-2 animate-slide-up sm:px-6">
      {/* ── Header / criar projeto ─────────────────────────────── */}
      <section className="glass rounded-2xl p-5 shadow-xl shadow-black/10 sm:rounded-3xl sm:p-8">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-[#a855f7] to-[#ec4899] shadow-[inset_0_1px_0_rgba(255,255,255,0.25)] sm:h-10 sm:w-10 sm:rounded-2xl">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
              </svg>
            </div>
            <div>
              <h1 className="text-lg font-semibold tracking-tight sm:text-xl">Projetos</h1>
              <p className="text-[12px] text-white/40 sm:text-[13px]">
                Cada projeto guarda o contexto da sua marca e agrupa vídeos, posts e carrosséis.
              </p>
            </div>
          </div>
          {!creating && (
            <button
              onClick={() => setCreating(true)}
              className="btn-gradient shrink-0 rounded-xl px-4 py-2.5 text-[13px] font-semibold text-white shadow-lg shadow-[#a855f7]/20 sm:px-5"
            >
              Novo projeto
            </button>
          )}
        </div>

        {creating && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (name.trim().length >= 2) createMutation.mutate();
            }}
            className="mt-5 space-y-3"
          >
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
              placeholder="Nome do projeto — ex.: Clínica Sorriso, Canal de Finanças..."
              className="w-full rounded-xl border border-white/[0.06] bg-white/[0.03] px-3.5 py-3 text-[14px] text-white/90 placeholder:text-white/20 transition-all duration-300 focus:border-[#a855f7]/40 focus:bg-white/[0.05] focus:shadow-[0_0_0_4px_rgba(168,85,247,0.08)]"
            />
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={6}
              placeholder={
                "Descreva tudo que a IA precisa saber para criar conteúdo com a sua cara:\n" +
                "• O que é o produto/marca e o que ela vende\n" +
                "• Público-alvo (quem é, dores, desejos)\n" +
                "• Tom de voz (descontraído, técnico, provocador...)\n" +
                "• Objetivos (vender, crescer perfil, autoridade) e ofertas ativas\n" +
                "• Diferenciais e o que NUNCA deve ser dito"
              }
              className="w-full resize-none rounded-xl border border-white/[0.06] bg-white/[0.03] p-3.5 text-[13px] leading-relaxed text-white/90 placeholder:text-white/20 transition-all duration-300 focus:border-[#a855f7]/40 focus:bg-white/[0.05] focus:shadow-[0_0_0_4px_rgba(168,85,247,0.08)] sm:rounded-2xl sm:p-4"
            />
            <div className="flex items-center justify-between">
              <p className="text-[11px] text-white/30">
                Esse contexto é usado em todos os vídeos, posts e carrosséis do projeto.
              </p>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setCreating(false)}
                  className="rounded-xl px-4 py-2.5 text-[13px] font-medium text-white/40 hover:text-white/70"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending || name.trim().length < 2}
                  className="btn-gradient rounded-xl px-5 py-2.5 text-[13px] font-semibold text-white shadow-lg shadow-[#a855f7]/20 disabled:opacity-30 disabled:shadow-none"
                >
                  {createMutation.isPending ? "Criando..." : "Criar projeto"}
                </button>
              </div>
            </div>
          </form>
        )}

        {(createMutation.error || error) && (
          <p className="mt-3 rounded-xl bg-[--red-soft] px-3.5 py-3 text-[12px] text-[#ff453a]">
            {(createMutation.error ?? error) instanceof Error
              ? ((createMutation.error ?? error) as Error).message
              : "Erro ao carregar projetos"}
          </p>
        )}
      </section>

      {/* ── Lista ─────────────────────────────────────────────── */}
      {workspaces.length === 0 && !creating ? (
        <div className="glass flex flex-col items-center justify-center rounded-2xl py-14 text-center sm:rounded-3xl">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-white/[0.04]">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-white/20">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
            </svg>
          </div>
          <p className="text-[13px] font-medium text-white/30 sm:text-[14px]">Nenhum projeto ainda</p>
          <p className="mt-1 text-[11px] text-white/20 sm:text-[12px]">
            Crie um projeto com o contexto da sua marca para gerar vídeos e posts consistentes.
          </p>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {workspaces.map((w, i) => (
            <Link
              key={w.id}
              href={`/workspaces/${w.id}`}
              className="glass glass-hover group rounded-2xl p-5 transition-all duration-300 animate-slide-up"
              style={{ animationDelay: `${i * 50}ms` }}
            >
              <div className="flex items-start justify-between gap-2">
                <p className="text-[15px] font-semibold tracking-tight text-white/90 transition-colors group-hover:text-white">
                  {w.name}
                </p>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mt-1 shrink-0 text-white/15 transition-all group-hover:translate-x-0.5 group-hover:text-white/30">
                  <polyline points="9 18 15 12 9 6" />
                </svg>
              </div>
              <p className="mt-1.5 line-clamp-2 text-[12px] leading-relaxed text-white/35">
                {w.description || "Sem descrição — adicione o contexto da marca."}
              </p>
              <div className="mt-4 flex items-center gap-3 text-[11px] text-white/30">
                <span className="rounded-full bg-white/[0.06] px-2.5 py-1">
                  {w.video_count} vídeo{w.video_count === 1 ? "" : "s"}
                </span>
                <span className="rounded-full bg-white/[0.06] px-2.5 py-1">
                  {w.post_count} post{w.post_count === 1 ? "" : "s"}
                </span>
                <span className="ml-auto text-white/20">
                  {new Date(w.created_at).toLocaleDateString("pt-BR")}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
