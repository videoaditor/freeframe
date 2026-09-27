/**
 * The glass folder from the upload references: neutral glass, one orange tab. Pure SVG so it is
 * crisp at any size and themeable through currentColor + CSS variables.
 */
export function FolderArt({ size = 112, label = 'FILES' }: { size?: number; label?: string }) {
  return (
    <svg width={size} height={size * 0.82} viewBox="0 0 140 115" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id="ff-back" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="var(--bg-hover)" />
          <stop offset="1" stopColor="var(--bg-tertiary)" />
        </linearGradient>
        <linearGradient id="ff-front" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="rgba(255,255,255,0.22)" />
          <stop offset="1" stopColor="rgba(255,255,255,0.06)" />
        </linearGradient>
      </defs>
      <path d="M8 18a10 10 0 0 1 10-10h32l12 12h60a10 10 0 0 1 10 10v67a10 10 0 0 1-10 10H18A10 10 0 0 1 8 97z" fill="url(#ff-back)" stroke="var(--glass-border)" />
      <rect x="22" y="26" width="96" height="58" rx="6" fill="var(--text-primary)" opacity="0.9" />
      <rect x="30" y="36" width="52" height="5" rx="2.5" fill="var(--bg-hover)" />
      <rect x="30" y="47" width="72" height="5" rx="2.5" fill="var(--bg-hover)" />
      <path d="M8 44a10 10 0 0 1 10-10h104a10 10 0 0 1 10 10v53a10 10 0 0 1-10 10H18A10 10 0 0 1 8 97z" fill="url(#ff-front)" stroke="rgba(255,255,255,0.18)" style={{ backdropFilter: 'blur(8px)' }} />
      <rect x="2" y="70" width="52" height="22" rx="6" fill="var(--accent)" />
      <text x="28" y="85.5" textAnchor="middle" fontSize="11" fontWeight="700" letterSpacing="1" fill="var(--text-inverse)" fontFamily="var(--font-sans)">{label}</text>
    </svg>
  )
}
