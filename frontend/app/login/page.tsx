"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import axios from "axios";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { LogoMark } from "@/components/Logo";

export default function LoginPage() {
  const router = useRouter();
  const { signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const { token, user } = await api.login({ email, password });
      signIn(token, user);
      const hasAccess = user.role === "admin" || user.subscription_status === "active";
      router.replace(hasAccess ? "/workspaces" : "/billing");
    } catch (err) {
      setError(
        axios.isAxiosError(err) && err.response?.data?.detail
          ? String(err.response.data.detail)
          : "Não foi possível entrar. Tente novamente.",
      );
      setSubmitting(false);
    }
  }

  return (
    <div className="hero-glow flex min-h-[80vh] items-center justify-center px-4 py-12">
      <div className="glass w-full max-w-sm rounded-3xl p-8 animate-scale-in">
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <LogoMark size={44} />
          <div>
            <h1 className="text-[20px] font-semibold tracking-tight">Entrar</h1>
            <p className="mt-1 text-[13px] text-white/40">
              Acesse sua conta para criar vídeos e posts
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            type="email"
            required
            autoComplete="email"
            placeholder="E-mail"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-xl border border-white/10 bg-white/[0.04] px-4 py-3 text-[14px] placeholder:text-white/25 focus:border-[#a855f7]/60"
          />
          <input
            type="password"
            required
            autoComplete="current-password"
            placeholder="Senha"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-xl border border-white/10 bg-white/[0.04] px-4 py-3 text-[14px] placeholder:text-white/25 focus:border-[#a855f7]/60"
          />
          {error && (
            <p className="rounded-xl bg-[--red-soft] px-4 py-2.5 text-[12px] text-[#ff453a]">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={submitting}
            className="btn-gradient w-full rounded-xl py-3 text-[14px] font-semibold text-white disabled:opacity-60"
          >
            {submitting ? "Entrando…" : "Entrar"}
          </button>
        </form>

        <p className="mt-5 text-center text-[13px] text-white/40">
          Ainda não tem conta?{" "}
          <Link href="/register" className="font-medium text-[#c084fc] hover:underline">
            Criar conta
          </Link>
        </p>
      </div>
    </div>
  );
}
