import Link from "next/link";
import { LogoMark } from "@/components/Logo";

// ── Dados de conteúdo ────────────────────────────────────────────────

const STEPS = [
  {
    number: "01",
    title: "Escreva a ideia",
    description:
      "Digite o tema do vídeo em uma frase. Só isso. Nada de roteiro, câmera ou software de edição.",
  },
  {
    number: "02",
    title: "A IA produz tudo",
    description:
      "Roteiro com gancho, narração profissional, imagens cinematográficas, legendas karaokê e edição — em minutos.",
  },
  {
    number: "03",
    title: "Publique e viralize",
    description:
      "Receba o vídeo vertical pronto com título, descrição e hashtags otimizadas para TikTok, Reels e Shorts.",
  },
];

const FEATURES = [
  {
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 20h9" /><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
      </svg>
    ),
    title: "Roteiro que prende",
    description: "Estrutura de retenção: gancho nos 3 primeiros segundos, desenvolvimento e chamada para ação.",
  },
  {
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" /><path d="M19 10v2a7 7 0 0 1-14 0v-10" transform="translate(0 2) scale(1 0.85)" /><line x1="12" y1="19" x2="12" y2="22" />
      </svg>
    ),
    title: "Narração com a sua voz",
    description: "Voz clonada ou narradores profissionais de IA, com entonação natural em português.",
  },
  {
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="18" height="18" rx="4" /><circle cx="8.5" cy="8.5" r="1.5" /><path d="m21 15-5-5L5 21" />
      </svg>
    ),
    title: "Imagens exclusivas",
    description: "Cada cena ganha uma imagem gerada por IA no seu estilo visual — sem banco de imagens repetido.",
  },
  {
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 7h16M4 12h10M4 17h7" />
      </svg>
    ),
    title: "Legendas karaokê",
    description: "Legendas palavra por palavra, sincronizadas com a narração, no estilo que mais retém audiência.",
  },
  {
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <polygon points="23 7 16 12 23 17 23 7" /><rect x="1" y="5" width="15" height="14" rx="2" />
      </svg>
    ),
    title: "Edição profissional",
    description: "Movimento de câmera, transições suaves, trilha sonora e mixagem de áudio automáticas.",
  },
  {
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 4h16v12H5.17L4 17.17V4Z" /><path d="M12 8v4M8 10h8" transform="scale(0.9) translate(1.3 0.5)" />
      </svg>
    ),
    title: "Otimizado por plataforma",
    description: "Título, descrição e hashtags gerados sob medida para TikTok, Instagram Reels e YouTube Shorts.",
  },
];

const PLANS = [
  {
    name: "Criador",
    price: "R$ 79",
    period: "/mês",
    description: "Para quem está começando a postar todo dia.",
    highlight: false,
    cta: "Começar agora",
    features: [
      "15 vídeos por mês",
      "Narração com vozes de IA",
      "Imagens geradas por IA",
      "Legendas karaokê",
      "Metadados para 3 plataformas",
    ],
  },
  {
    name: "Profissional",
    price: "R$ 149",
    period: "/mês",
    description: "Para criadores que vivem de conteúdo.",
    highlight: true,
    cta: "Assinar Profissional",
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
    name: "Estúdio",
    price: "R$ 399",
    period: "/mês",
    description: "Para agências e times com vários canais.",
    highlight: false,
    cta: "Falar com vendas",
    features: [
      "Vídeos ilimitados",
      "Múltiplas vozes clonadas",
      "Vários perfis e canais",
      "Publicação automática (em breve)",
      "Gerente de conta dedicado",
    ],
  },
];

const FAQS = [
  {
    q: "Preciso saber editar vídeo?",
    a: "Não. Você só escreve a ideia — a plataforma cuida do roteiro, narração, imagens, legendas e edição final. O vídeo sai pronto para publicar.",
  },
  {
    q: "Os vídeos parecem feitos por IA?",
    a: "Cada vídeo tem imagens exclusivas geradas para o seu tema, narração natural e edição com movimento de câmera e trilha. Você ainda pode revisar roteiro e imagens antes da renderização.",
  },
  {
    q: "Posso usar a minha própria voz?",
    a: "Sim. No plano Profissional você clona a sua voz e todos os vídeos são narrados com ela, mantendo a identidade do seu canal.",
  },
  {
    q: "Posso cancelar quando quiser?",
    a: "Sim. A assinatura é mensal, sem fidelidade. Os vídeos já gerados continuam sendo seus para sempre.",
  },
];

// ── Componentes ──────────────────────────────────────────────────────

function SectionTitle({ eyebrow, title, subtitle }: { eyebrow: string; title: string; subtitle?: string }) {
  return (
    <div className="mx-auto max-w-2xl text-center">
      <span className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#c084fc] sm:text-[12px]">
        {eyebrow}
      </span>
      <h2 className="mt-3 text-[26px] font-semibold leading-tight tracking-tight sm:text-[34px]">
        {title}
      </h2>
      {subtitle && (
        <p className="mt-3 text-[14px] leading-relaxed text-white/40 sm:text-[15px]">{subtitle}</p>
      )}
    </div>
  );
}

function IconCheckSmall() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="mt-0.5 shrink-0 text-[#30d158]">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

export default function LandingPage() {
  return (
    <div className="hero-glow">
      {/* ── Hero ───────────────────────────────────────────── */}
      <section className="mx-auto max-w-[1080px] px-4 pb-20 pt-14 text-center sm:px-6 sm:pb-28 sm:pt-24">
        <div className="animate-slide-up">
          <div className="mx-auto mb-6 flex w-fit animate-float">
            <LogoMark size={64} />
          </div>
          <span className="glass inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 text-[11px] font-medium text-white/55 sm:text-[12px]">
            <span className="h-1.5 w-1.5 rounded-full bg-[#30d158]" />
            Vídeos gerados por IA em minutos
          </span>
          <h1 className="mx-auto mt-6 max-w-3xl text-[36px] font-semibold leading-[1.08] tracking-tight sm:text-[56px]">
            Uma ideia entra.
            <br />
            <span className="text-gradient">Um vídeo viral sai.</span>
          </h1>
          <p className="mx-auto mt-5 max-w-xl text-[15px] leading-relaxed text-white/45 sm:text-[17px]">
            Escreva o tema em uma frase e receba um vídeo vertical completo — roteiro,
            narração, imagens, legendas e edição — pronto para TikTok, Reels e Shorts.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              href="/workspaces"
              className="btn-gradient w-full rounded-full px-8 py-3.5 text-[14px] font-semibold text-white shadow-xl shadow-[#a855f7]/25 sm:w-auto"
            >
              Criar meu primeiro vídeo
            </Link>
            <Link
              href="/#planos"
              className="glass glass-hover w-full rounded-full px-8 py-3.5 text-[14px] font-medium text-white/70 transition-all sm:w-auto"
            >
              Ver planos
            </Link>
          </div>
          <p className="mt-4 text-[11px] text-white/25 sm:text-[12px]">
            Sem cartão de crédito para testar · Cancele quando quiser
          </p>
        </div>
      </section>

      {/* ── Como funciona ──────────────────────────────────── */}
      <section id="como-funciona" className="mx-auto max-w-[1080px] scroll-mt-24 px-4 py-16 sm:px-6 sm:py-24">
        <SectionTitle
          eyebrow="Como funciona"
          title="Do tema ao vídeo pronto em 3 passos"
          subtitle="Todo o trabalho pesado de produção acontece automaticamente, nos bastidores."
        />
        <div className="mt-10 grid gap-4 sm:mt-14 sm:grid-cols-3 sm:gap-5">
          {STEPS.map((step) => (
            <div key={step.number} className="glass rounded-2xl p-6 sm:rounded-3xl sm:p-8">
              <span className="text-gradient text-[28px] font-semibold tracking-tight sm:text-[32px]">
                {step.number}
              </span>
              <h3 className="mt-3 text-[16px] font-semibold tracking-tight sm:text-[17px]">
                {step.title}
              </h3>
              <p className="mt-2 text-[13px] leading-relaxed text-white/40 sm:text-[14px]">
                {step.description}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Recursos ───────────────────────────────────────── */}
      <section id="recursos" className="mx-auto max-w-[1080px] scroll-mt-24 px-4 py-16 sm:px-6 sm:py-24">
        <SectionTitle
          eyebrow="Recursos"
          title="Um estúdio de produção completo"
          subtitle="Tudo que uma equipe de produção faria, condensado em uma assinatura."
        />
        <div className="mt-10 grid gap-4 sm:mt-14 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature) => (
            <div key={feature.title} className="glass glass-hover rounded-2xl p-5 transition-all sm:rounded-3xl sm:p-6">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-[#a855f7]/20 to-[#ec4899]/20 text-[#c084fc]">
                {feature.icon}
              </div>
              <h3 className="mt-4 text-[15px] font-semibold tracking-tight">{feature.title}</h3>
              <p className="mt-1.5 text-[13px] leading-relaxed text-white/40">{feature.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Planos ─────────────────────────────────────────── */}
      <section id="planos" className="mx-auto max-w-[1080px] scroll-mt-24 px-4 py-16 sm:px-6 sm:py-24">
        <SectionTitle
          eyebrow="Planos"
          title="Assine e produza todos os dias"
          subtitle="Menos que o custo de um único editor freelancer — para um mês inteiro de conteúdo."
        />
        <div className="mt-10 grid gap-4 sm:mt-14 lg:grid-cols-3 lg:items-stretch">
          {PLANS.map((plan) => (
            <div
              key={plan.name}
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
                <span className="text-[36px] font-semibold tracking-tight sm:text-[40px]">{plan.price}</span>
                <span className="text-[13px] text-white/35">{plan.period}</span>
              </div>
              <p className="mt-1.5 text-[13px] text-white/40">{plan.description}</p>
              <ul className="mt-6 flex-1 space-y-2.5">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-start gap-2.5 text-[13px] text-white/60">
                    <IconCheckSmall />
                    {feature}
                  </li>
                ))}
              </ul>
              <Link
                href="/register"
                className={`mt-8 block rounded-xl py-3 text-center text-[13px] font-semibold transition-all ${
                  plan.highlight
                    ? "btn-gradient text-white shadow-lg shadow-[#a855f7]/20"
                    : "glass glass-hover text-white/70"
                }`}
              >
                {plan.cta}
              </Link>
            </div>
          ))}
        </div>
      </section>

      {/* ── FAQ ────────────────────────────────────────────── */}
      <section className="mx-auto max-w-[760px] px-4 py-16 sm:px-6 sm:py-24">
        <SectionTitle eyebrow="Dúvidas" title="Perguntas frequentes" />
        <div className="mt-10 space-y-3 sm:mt-12">
          {FAQS.map((faq) => (
            <details key={faq.q} className="glass group rounded-2xl px-5 py-4 sm:px-6">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-[14px] font-medium text-white/80 sm:text-[15px] [&::-webkit-details-marker]:hidden">
                {faq.q}
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0 text-white/30 transition-transform group-open:rotate-45">
                  <path d="M12 5v14M5 12h14" />
                </svg>
              </summary>
              <p className="mt-3 text-[13px] leading-relaxed text-white/45 sm:text-[14px]">{faq.a}</p>
            </details>
          ))}
        </div>
      </section>

      {/* ── CTA final ──────────────────────────────────────── */}
      <section className="mx-auto max-w-[1080px] px-4 pb-16 sm:px-6 sm:pb-24">
        <div className="glass relative overflow-hidden rounded-3xl px-6 py-14 text-center sm:py-20">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(400px_200px_at_50%_0%,rgba(168,85,247,0.18),transparent_70%)]" />
          <h2 className="relative text-[26px] font-semibold leading-tight tracking-tight sm:text-[36px]">
            Seu próximo vídeo viral
            <br />
            <span className="text-gradient">começa com uma frase.</span>
          </h2>
          <p className="relative mx-auto mt-4 max-w-md text-[14px] leading-relaxed text-white/40 sm:text-[15px]">
            Enquanto você lê isso, outros criadores estão publicando. Comece agora.
          </p>
          <Link
            href="/workspaces"
            className="btn-gradient relative mt-8 inline-block rounded-full px-8 py-3.5 text-[14px] font-semibold text-white shadow-xl shadow-[#a855f7]/25"
          >
            Criar meu primeiro vídeo
          </Link>
        </div>
      </section>

      {/* ── Footer ─────────────────────────────────────────── */}
      <footer className="border-t border-white/[0.06]">
        <div className="mx-auto flex max-w-[1080px] flex-col items-center justify-between gap-4 px-4 py-8 sm:flex-row sm:px-6">
          <div className="flex items-center gap-2.5">
            <LogoMark size={20} />
            <span className="text-[13px] font-semibold tracking-tight">
              feed<span className="text-gradient">eo</span>
            </span>
          </div>
          <div className="flex flex-col items-center gap-2 sm:flex-row sm:gap-4">
            <Link
              href="/privacidade"
              className="text-[11px] text-white/35 transition hover:text-white/60 sm:text-[12px]"
            >
              Política de Privacidade
            </Link>
            <p className="text-[11px] text-white/25 sm:text-[12px]">
              © {new Date().getFullYear()} feedeo — Vídeos virais gerados por IA.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
