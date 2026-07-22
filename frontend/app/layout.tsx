import type { Metadata, Viewport } from "next";
import Providers from "@/lib/providers";
import Header from "@/components/Header";
import "./globals.css";

export const metadata: Metadata = {
  title: "virou.ai — Seu vídeo pronto para viralizar",
  description:
    "Transforme uma ideia em um vídeo vertical completo com IA: roteiro, narração, imagens, legendas e edição. Pronto para TikTok, Reels e Shorts.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  viewportFit: "cover",
  themeColor: "#000000",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body className="min-h-dvh">
        <Providers>
          <Header />
          <main>{children}</main>
        </Providers>
      </body>
    </html>
  );
}
