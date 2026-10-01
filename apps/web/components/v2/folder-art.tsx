import { useId } from 'react'

/**
 * The folder from the upload references (glossy, dimensional), in the Aditor coral of the logo:
 * a lit back panel, a sheet of paper peeking out, a frosted front with a top highlight, a soft
 * contact shadow and a label chip. Pure SVG: crisp at any size, no image request.
 */
export function FolderArt({ size = 112, label = 'FILES' }: { size?: number; label?: string }) {
  const id = useId()
  return (
    <svg width={size} height={size * 0.84} viewBox="0 0 160 134" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id={`${id}-back`} x1="0" y1="0" x2="0.3" y2="1">
          <stop offset="0" stopColor="var(--folder-back-top, #ff8a6a)" />
          <stop offset="1" stopColor="var(--folder-back-bottom, #e5432b)" />
        </linearGradient>
        <linearGradient id={`${id}-front`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="var(--folder-front-top, #ffb39f)" stopOpacity="0.92" />
          <stop offset="1" stopColor="var(--folder-front-bottom, #ff6b4f)" stopOpacity="0.88" />
        </linearGradient>
        <linearGradient id={`${id}-shine`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#fff" stopOpacity="0.55" />
          <stop offset="0.35" stopColor="#fff" stopOpacity="0" />
        </linearGradient>
        <filter id={`${id}-shadow`} x="-20%" y="-20%" width="140%" height="160%">
          <feGaussianBlur stdDeviation="6" />
        </filter>
      </defs>
      <ellipse cx="82" cy="122" rx="54" ry="7" fill="#000" opacity="0.45" filter={`url(#${id}-shadow)`} />
      <path d="M16 20c0-6 4.5-10 10-10h30c3 0 5 1 7 3l8 8h63c6 0 10 4.5 10 10v72c0 6-4.5 10-10 10H26c-5.5 0-10-4-10-10z" fill={`url(#${id}-back)`} />
      <g transform="rotate(-4 80 56)">
        <rect x="32" y="26" width="92" height="62" rx="6" fill="#fff" />
        <rect x="42" y="37" width="48" height="5" rx="2.5" fill="#e6e6ea" />
        <rect x="42" y="48" width="68" height="5" rx="2.5" fill="#efeff2" />
        <rect x="42" y="59" width="58" height="5" rx="2.5" fill="#efeff2" />
      </g>
      <path d="M12 50c0-5.5 4.5-10 10-10h116c5.5 0 10 4.5 10 10v52c0 6-4.5 10-10 10H22c-5.5 0-10-4-10-10z" fill={`url(#${id}-front)`} />
      <path d="M12 50c0-5.5 4.5-10 10-10h116c5.5 0 10 4.5 10 10v52c0 6-4.5 10-10 10H22c-5.5 0-10-4-10-10z" fill={`url(#${id}-shine)`} />
      <path d="M22 40.75h116c5 0 9.25 4 9.25 9.25" stroke="#fff" strokeOpacity="0.7" strokeWidth="1.5" strokeLinecap="round" />
      {label && <g><rect x="4" y="80" width="56" height="24" rx="8" fill="#141416" />
      <rect x="4.5" y="80.5" width="55" height="23" rx="7.5" stroke="#fff" strokeOpacity="0.14" />
      <text x="32" y="96.5" textAnchor="middle" fontSize="11" fontWeight="700" letterSpacing="1.2" fill="#fff" fontFamily="var(--font-sans)">{label}</text></g>}
    </svg>
  )
}
