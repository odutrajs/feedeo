"use client";

import { useQuery } from "@tanstack/react-query";
import { api, MediaInsights } from "@/lib/api";

// ── Helpers ──────────────────────────────────────────────────────────

export function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function formatWatchTime(ms: number): string {
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const minutes = Math.floor(seconds / 60);
  const secs = seconds - minutes * 60;
  return `${minutes}m${secs.toFixed(0).padStart(2, "0")}s`;
}

// ── Metric Row Item ─────────────────────────────────────────────────

function MetricItem({
  label,
  value,
  icon,
  color = "text-white/80",
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
  color?: string;
}) {
  return (
    <div className="flex items-center gap-1.5 min-w-0">
      <span className="shrink-0 opacity-80">{icon}</span>
      <span className={`text-[13px] font-semibold tabular-nums leading-none ${color}`}>
        {value}
      </span>
      <span className="hidden text-[9px] font-medium uppercase tracking-wide text-white/25 sm:inline">
        {label}
      </span>
    </div>
  );
}

// ── Icons (12px for compact layout) ─────────────────────────────────

const ICONS = {
  views: (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#64d2ff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" />
    </svg>
  ),
  reach: (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#30d158" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  ),
  likes: (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="#ff375f" stroke="none">
      <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
    </svg>
  ),
  comments: (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#ff9f0a" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  ),
  shares: (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#bf5af2" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" /><line x1="8.59" y1="13.51" x2="15.42" y2="17.49" /><line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
    </svg>
  ),
  saved: (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#ffd60a" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
    </svg>
  ),
};

// ── Insights Grid ───────────────────────────────────────────────────

function InsightsGrid({ insights, isReel }: { insights: MediaInsights; isReel: boolean }) {
  return (
    <div className="space-y-3 animate-scale-in">
      {/* Métricas principais — layout compacto que cabe em cards estreitos */}
      <div className="grid grid-cols-3 gap-x-3 gap-y-2.5 rounded-xl bg-white/[0.03] px-3 py-3">
        <MetricItem label="Views" value={formatNumber(insights.views)} color="text-[#64d2ff]" icon={ICONS.views} />
        <MetricItem label="Alcance" value={formatNumber(insights.reach)} color="text-[#30d158]" icon={ICONS.reach} />
        <MetricItem label="Curtidas" value={formatNumber(insights.likes)} color="text-[#ff375f]" icon={ICONS.likes} />
        <MetricItem label="Coment." value={formatNumber(insights.comments)} color="text-[#ff9f0a]" icon={ICONS.comments} />
        <MetricItem label="Compart." value={formatNumber(insights.shares)} color="text-[#bf5af2]" icon={ICONS.shares} />
        <MetricItem label="Salvos" value={formatNumber(insights.saved)} color="text-[#ffd60a]" icon={ICONS.saved} />
      </div>

      {/* Retenção (só Reels) */}
      {isReel && (insights.avg_watch_time_ms > 0 || insights.video_view_total_time_ms > 0) && (
        <div className="rounded-xl bg-white/[0.03] px-3 py-3 space-y-2">
          <p className="text-[9px] font-semibold uppercase tracking-widest text-white/25">
            Retenção
          </p>
          <div className="flex flex-wrap gap-x-4 gap-y-1.5">
            {insights.avg_watch_time_ms > 0 && (
              <div className="flex items-baseline gap-1.5">
                <span className="text-[13px] font-semibold text-[#64d2ff] tabular-nums">
                  {formatWatchTime(insights.avg_watch_time_ms)}
                </span>
                <span className="text-[9px] text-white/30">média</span>
              </div>
            )}
            {insights.video_view_total_time_ms > 0 && (
              <div className="flex items-baseline gap-1.5">
                <span className="text-[13px] font-semibold text-[#c084fc] tabular-nums">
                  {formatWatchTime(insights.video_view_total_time_ms)}
                </span>
                <span className="text-[9px] text-white/30">total</span>
              </div>
            )}
            {insights.total_interactions > 0 && (
              <div className="flex items-baseline gap-1.5">
                <span className="text-[13px] font-semibold text-[#30d158] tabular-nums">
                  {formatNumber(insights.total_interactions)}
                </span>
                <span className="text-[9px] text-white/30">interações</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main Panel (fetches data by publication ID) ─────────────────────

export default function InsightsPanel({ pubId }: { pubId: number }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["publication_insights", pubId],
    queryFn: () => api.getPublicationInsights(pubId),
    staleTime: 60_000,
    retry: 1,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-4">
        <svg className="h-4 w-4 animate-spin text-white/20" viewBox="0 0 24 24" fill="none">
          <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
        </svg>
      </div>
    );
  }

  if (error || !data) {
    return (
      <p className="py-2 text-center text-[11px] text-white/25">
        Insights ainda não disponíveis. Dados podem levar até 48h.
      </p>
    );
  }

  const { insights, media_info } = data;
  const isReel = media_info?.media_product_type?.toUpperCase() === "REELS";

  return (
    <div className="space-y-2">
      <InsightsGrid insights={insights} isReel={isReel} />

      {media_info?.permalink && (
        <a
          href={media_info.permalink}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-[11px] text-[#c084fc] transition-colors hover:text-[#d8b4fe]"
        >
          Ver publicação no Instagram →
        </a>
      )}
    </div>
  );
}
