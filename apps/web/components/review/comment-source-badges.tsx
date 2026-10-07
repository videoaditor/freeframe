import type { ReviewSource } from '@/types'

export function CommentSourceBadges({ source }: { source?: ReviewSource | null }) {
  const order = ['basics', 'brand', 'briefing'] as const
  if (source?.schema_version !== 'autoreview.comment-source.v1' || !source.requirement_id ||
      !Array.isArray(source.sources) || !source.sources.length || source.sources.length > 8 ||
      source.sources.some(s => !s || !order.includes(s.layer) || !s.reference_id || !s.source_version)) return null
  const layers = order.filter(layer => source.sources.some(s => s.layer === layer))
  return (
    <span aria-label="Requirement sources" className="flex flex-wrap gap-1">
      {layers.map(layer => (
        <span key={layer} className="comment-source-label rounded px-2 py-0.5 text-[0.6875rem] font-medium leading-4">
          {{ basics: 'Basics', brand: 'Brand', briefing: 'Briefing' }[layer]}
        </span>
      ))}
    </span>
  )
}
