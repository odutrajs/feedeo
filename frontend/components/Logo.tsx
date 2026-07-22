export function LogoMark({ size = 26 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      aria-hidden="true"
      className="shrink-0"
    >
      <defs>
        <linearGradient id="virou-g" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
          <stop stopColor="#a855f7" />
          <stop offset="1" stopColor="#ec4899" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="17" fill="url(#virou-g)" />
      <rect width="64" height="64" rx="17" fill="url(#virou-g)" style={{ mixBlendMode: "overlay" }} opacity="0.35" />
      {/* Arco de rotação: a ideia "virando" vídeo */}
      <circle
        cx="32"
        cy="32"
        r="17"
        stroke="white"
        strokeWidth="4.5"
        strokeLinecap="round"
        strokeDasharray="80 27"
        strokeDashoffset="-8"
        opacity="0.95"
        transform="rotate(-45 32 32)"
      />
      {/* Play */}
      <path d="M27 24.5c0-1.6 1.75-2.58 3.1-1.74l11.2 6.98a2.05 2.05 0 0 1 0 3.48l-11.2 6.98c-1.35.84-3.1-.14-3.1-1.74V24.5z" fill="white" />
    </svg>
  );
}

export function LogoWordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`font-semibold tracking-tight ${className}`}>
      virou
      <span className="bg-gradient-to-r from-[#a855f7] to-[#ec4899] bg-clip-text text-transparent">
        .ai
      </span>
    </span>
  );
}

export default function Logo({ size = 26, textClassName = "text-[15px]" }: { size?: number; textClassName?: string }) {
  return (
    <span className="flex items-center gap-2.5">
      <LogoMark size={size} />
      <LogoWordmark className={textClassName} />
    </span>
  );
}
