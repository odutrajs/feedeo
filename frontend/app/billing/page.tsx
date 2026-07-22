"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import axios from "axios";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const PLANS = [
  {
    id: "creator",
    name: "Criador",
    price: "R$ 79",
    period: "/mês",
    description: "Para quem está começando a postar todo dia.",
    highlight: false,
    features: [
      "15 vídeos por mês",
      "Narração com vozes de IA",
      "Imagens geradas por IA",
      "Legendas karaokê",
      "Metadados para 3 plataformas",
    ],
  },
  {
    id: "pro",
    name: "Profissional",
    price: "R$ 149",
    period: "/mês",
    description: "Para criadores que vivem de conteúdo.",
    highlight: true,
    features: [
      "50 vídeos por mês",
      "Clonagem da sua voz",
      "Estilos visuais personalizados",
      "Revisão de roteiro e imagens",
      "Trilha sonora e mixagem",
      "Suporte prioritário",
    ],
  },
  {
    id: "studio",
    name: "Estúdio",
    price: "R$ 399",
    period: "/mês",
    description: "Para agências e times com vários canais.",
    highlight: false,
    features: [
      "Vídeos ilimitados",
      "Múltiplas vozes clonadas",
      "Vários perfis e canais",
      "Publicação automática",
      "Gerente de conta dedicado",
    ],
  },
];

const STATUS_LABEL: Record<string, string> = {
  active: "Ativa",
  past_due: "Pagamento pendente",
  canceled: "Cancelada",
  none: "Sem assinatura",
};

function IconCheck() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="mt-0.5 shrink-0 text-[#30d158]">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function BillingContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, loading, refresh, signOut } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [busyPlan, setBusyPlan] = useState<string | null>(null);

  const checkoutStatus = searchParams.get("status"); // success | cancelled

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  // Depois do checkout, o webhook atualiza o status — recarrega o /me
  useEffect(() => {
    if (checkoutStatus === "success") {
      const timer = setInterval(() => void refresh(), 2500);
      return () => clearInterval(timer);
    }
  }, [checkoutStatus, refresh]);

  if (loading || !user) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-white/15 border-t-[#a855f7]" />
      </div>
    );
  }

  const isActive = user.subscription_status === "active" || user.role === "admin";

  async function subscribe(plan: string) {
    setError(null);
    setBusyPlan(plan);
    try {
      const { url } = await api.createCheckout(plan);
      window.location.href = url;
    } catch (err) {
      setError(
        axios.isAxiosError(err) && err.response?.data?.detail
          ? String(err.response.data.detail)
          : "Não foi possível iniciar o checkout.",
      );
      setBusyPlan(null);
    }
  }

  async function openPortal() {
    setError(null);
    try {
      const { url } = await api.createBillingPortal();
      window.location.href = url;
    } catch (err) {
      setError(
        axios.isAxiosError(err) && err.response?.data?.detail
          ? String(err.response.data.detail)
          : "Não foi possível abrir o portal de assinatura.",
      );
    }
  }

  return (
    <div className="mx-auto max-w-[1080px] px-4 pb-20 pt-6 sm:px-6 animate-slide-up">
      {/* ── Status da conta ─────────────────────────────────── */}
      <section className="glass rounded-3xl p-6 sm:p-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-[22px] font-semibold tracking-tight sm:text-[26px]">
              Assinatura
            </h1>
            <p className="mt-1 text-[13px] text-white/40">
              Conectado como <span className="text-white/70">{user.email}</span>
              {" · "}
              <button onClick={() => { signOut(); router.replace("/login"); }} className="text-[#c084fc] hover:underline">
                sair
              </button>
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span
              className={`inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-[12px] font-semibold ${
                isActive
                  ? "bg-[--green-soft] text-[#30d158]"
                  : user.subscription_status === "past_due"
                    ? "bg-[--orange-soft] text-[#ff9f0a]"
                    : "bg-white/[0.06] text-white/50"
              }`}
            >
              <span className={`h-1.5 w-1.5 rounded-full ${isActive ? "bg-[#30d158]" : "bg-white/30"}`} />
              {user.role === "admin" ? "Admin" : STATUS_LABEL[user.subscription_status] ?? user.subscription_status}
              {user.plan && isActive && ` · ${PLANS.find((p) => p.id === user.plan)?.name ?? user.plan}`}
            </span>
            {isActive && user.role !== "admin" && (
              <button
                onClick={openPortal}
                className="glass glass-hover rounded-full px-4 py-1.5 text-[12px] font-medium text-white/70"
              >
                Gerenciar assinatura
              </button>
            )}
          </div>
        </div>

        {checkoutStatus === "success" && !isActive && (
          <p className="mt-4 rounded-xl bg-[--green-soft] px-4 py-3 text-[13px] text-[#30d158]">
            Pagamento recebido! Aguardando confirmação do Stripe… esta página atualiza sozinha.
          </p>
        )}
        {checkoutStatus === "cancelled" && (
          <p className="mt-4 rounded-xl bg-[--orange-soft] px-4 py-3 text-[13px] text-[#ff9f0a]">
            Checkout cancelado. Escolha um plano quando quiser continuar.
          </p>
        )}
        {error && (
          <p className="mt-4 rounded-xl bg-[--red-soft] px-4 py-3 text-[13px] text-[#ff453a]">
            {error}
          </p>
        )}

        {isActive && (
          <div className="mt-6 flex flex-col gap-3 sm:flex-row">
            <button
              onClick={() => router.push("/workspaces")}
              className="btn-gradient rounded-xl px-6 py-3 text-[13px] font-semibold text-white"
            >
              Ir para meus projetos
            </button>
          </div>
        )}
      </section>

      {/* ── Planos ──────────────────────────────────────────── */}
      {!isActive && (
        <section className="mt-8">
          <h2 className="text-center text-[20px] font-semibold tracking-tight sm:text-[24px]">
            Escolha seu plano para começar
          </h2>
          <p className="mt-2 text-center text-[13px] text-white/40">
            Assinatura mensal via Stripe, sem fidelidade. Cancele quando quiser.
          </p>
          <div className="mt-8 grid gap-4 lg:grid-cols-3 lg:items-stretch">
            {PLANS.map((plan) => (
              <div
                key={plan.id}
                className={`relative flex flex-col rounded-3xl p-6 sm:p-8 ${
                  plan.highlight
                    ? "border border-[#a855f7]/40 bg-gradient-to-b from-[#a855f7]/[0.12] to-[#ec4899]/[0.04] shadow-2xl shadow-[#a855f7]/10"
                    : "glass"
                }`}
              >
                {plan.highlight && (
                  <span className="btn-gradient absolute -top-3 left-1/2 -translate-x-1/2 rounded-full px-3.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-white">
                    Mais popular
                  </span>
                )}
                <h3 className="text-[15px] font-semibold tracking-tight text-white/80">{plan.name}</h3>
                <div className="mt-3 flex items-baseline gap-1">
                  <span className="text-[36px] font-semibold tracking-tight">{plan.price}</span>
                  <span className="text-[13px] text-white/35">{plan.period}</span>
                </div>
                <p className="mt-1.5 text-[13px] text-white/40">{plan.description}</p>
                <ul className="mt-6 flex-1 space-y-2.5">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-start gap-2.5 text-[13px] text-white/60">
                      <IconCheck />
                      {feature}
                    </li>
                  ))}
                </ul>
                <button
                  onClick={() => subscribe(plan.id)}
                  disabled={busyPlan !== null}
                  className={`mt-8 block rounded-xl py-3 text-center text-[13px] font-semibold transition-all disabled:opacity-60 ${
                    plan.highlight
                      ? "btn-gradient text-white shadow-lg shadow-[#a855f7]/20"
                      : "glass glass-hover text-white/70"
                  }`}
                >
                  {busyPlan === plan.id ? "Redirecionando…" : `Assinar ${plan.name}`}
                </button>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

export default function BillingPage() {
  return (
    <Suspense>
      <BillingContent />
    </Suspense>
  );
}
