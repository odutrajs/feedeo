"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import Logo from "@/components/Logo";
import { useAuth } from "@/lib/auth";

const PLAN_LABELS: Record<string, string> = {
  creator: "Criador",
  pro: "Profissional",
  studio: "Estúdio",
};

export default function Header() {
  const { user, loading, signOut } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Fecha o menu ao clicar fora ou trocar de página
  useEffect(() => setMenuOpen(false), [pathname]);
  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const hasAccess = !!user && (user.role === "admin" || user.subscription_status === "active");
  const initials = user?.name
    ?.split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <header className="sticky top-0 z-50">
      <div className="mx-auto max-w-[1080px] px-4 py-3 sm:px-6 sm:py-4">
        <div className="glass flex items-center justify-between rounded-full px-4 py-2 shadow-lg shadow-black/20 sm:px-5 sm:py-2.5">
          <Link href={hasAccess ? "/workspaces" : "/"} className="transition-opacity hover:opacity-80">
            <Logo size={24} textClassName="text-[14px] sm:text-[15px]" />
          </Link>

          {/* ── Navegação central ─────────────────────────── */}
          {user && hasAccess ? (
            <nav className="hidden items-center gap-5 text-[12px] font-medium text-white/45 md:flex">
              <Link href="/workspaces" className={`transition-colors hover:text-white/80 ${pathname.startsWith("/workspaces") || pathname.startsWith("/projects") ? "text-white/90" : ""}`}>
                Meus projetos
              </Link>
              <Link href="/billing" className={`transition-colors hover:text-white/80 ${pathname.startsWith("/billing") ? "text-white/90" : ""}`}>
                Assinatura
              </Link>
            </nav>
          ) : (
            <nav className="hidden items-center gap-5 text-[12px] font-medium text-white/45 md:flex">
              <Link href="/#como-funciona" className="transition-colors hover:text-white/80">
                Como funciona
              </Link>
              <Link href="/#recursos" className="transition-colors hover:text-white/80">
                Recursos
              </Link>
              <Link href="/#planos" className="transition-colors hover:text-white/80">
                Planos
              </Link>
            </nav>
          )}

          {/* ── Lado direito: sessão ──────────────────────── */}
          {loading ? (
            <div className="h-8 w-8 rounded-full bg-white/[0.06]" />
          ) : user ? (
            <div className="relative" ref={menuRef}>
              <button
                onClick={() => setMenuOpen((v) => !v)}
                className="flex items-center gap-2 rounded-full py-1 pl-1 pr-2 transition-colors hover:bg-white/[0.06]"
              >
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-[#a855f7] to-[#ec4899] text-[11px] font-semibold text-white">
                  {initials || "?"}
                </span>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className={`text-white/40 transition-transform ${menuOpen ? "rotate-180" : ""}`}>
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </button>

              {menuOpen && (
                <div className="glass absolute right-0 top-full mt-2 w-64 rounded-2xl p-2 shadow-2xl shadow-black/40 animate-scale-in" style={{ background: "rgba(20,20,22,0.92)" }}>
                  <div className="border-b border-white/[0.06] px-3 py-2.5">
                    <p className="truncate text-[13px] font-semibold text-white/90">{user.name}</p>
                    <p className="truncate text-[11px] text-white/35">{user.email}</p>
                    <span
                      className={`mt-2 inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[10px] font-semibold ${
                        hasAccess ? "bg-[--green-soft] text-[#30d158]" : "bg-[--orange-soft] text-[#ff9f0a]"
                      }`}
                    >
                      <span className={`h-1 w-1 rounded-full ${hasAccess ? "bg-[#30d158]" : "bg-[#ff9f0a]"}`} />
                      {user.role === "admin"
                        ? "Admin"
                        : hasAccess
                          ? `Plano ${PLAN_LABELS[user.plan ?? ""] ?? user.plan ?? "ativo"}`
                          : "Assinatura pendente"}
                    </span>
                  </div>

                  <nav className="mt-1 flex flex-col text-[13px] text-white/70">
                    {hasAccess && (
                      <>
                        <Link href="/workspaces" className="rounded-xl px-3 py-2 transition-colors hover:bg-white/[0.06] hover:text-white">
                          Meus projetos
                        </Link>
                      </>
                    )}
                    <Link href="/billing" className="rounded-xl px-3 py-2 transition-colors hover:bg-white/[0.06] hover:text-white">
                      Assinatura e pagamento
                    </Link>
                    <button
                      onClick={() => {
                        signOut();
                        router.replace("/login");
                      }}
                      className="rounded-xl px-3 py-2 text-left text-[#ff453a]/80 transition-colors hover:bg-[--red-soft] hover:text-[#ff453a]"
                    >
                      Sair
                    </button>
                  </nav>
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <Link
                href="/login"
                className="text-[12px] font-medium text-white/50 transition-colors hover:text-white/90"
              >
                Entrar
              </Link>
              <Link
                href="/register"
                className="btn-gradient rounded-full px-4 py-1.5 text-[12px] font-semibold text-white sm:px-5 sm:py-2"
              >
                Criar conta
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
