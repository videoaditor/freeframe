'use client'

import * as React from 'react'
import { cn } from '@/lib/utils'
import { FolderArt } from './folder-art'

interface DropZoneProps {
  onFiles: (files: File[]) => void
  accept?: string
  multiple?: boolean
  title: string
  hint?: string
  disabled?: boolean
  compact?: boolean
  className?: string
}

/**
 * One big target (Fitts): the whole card is the button. Drag a file over it and it wakes up; click,
 * Enter or Space opens the picker. Keyboard and screen readers get a real button.
 */
export function DropZone({ onFiles, accept = 'video/*', multiple = false, title, hint, disabled, compact, className }: DropZoneProps) {
  const input = React.useRef<HTMLInputElement>(null)
  const [hot, setHot] = React.useState(false)
  const depth = React.useRef(0)

  const take = (list: FileList | null) => {
    const files = Array.from(list || [])
    if (files.length && !disabled) onFiles(multiple ? files : files.slice(0, 1))
  }

  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => input.current?.click()}
      onDragEnter={(e) => { e.preventDefault(); depth.current++; setHot(true) }}
      onDragOver={(e) => e.preventDefault()}
      onDragLeave={() => { depth.current = Math.max(0, depth.current - 1); if (!depth.current) setHot(false) }}
      onDrop={(e) => { e.preventDefault(); depth.current = 0; setHot(false); take(e.dataTransfer.files) }}
      className={cn(
        'drop-idle group relative flex w-full flex-col items-center justify-center rounded-[var(--radius-xl)] border border-dashed border-[var(--drop-border)]',
        'bg-bg-secondary/60 text-center outline-none focus-visible:ring-2 focus-visible:ring-accent/60 disabled:opacity-50',
        compact ? 'gap-3 px-6 py-8' : 'gap-5 px-8 py-14 sm:py-16',
        hot && 'drop-hot',
        className,
      )}
      aria-label={title}
    >
      <span className="folder-lift">
        <FolderArt size={compact ? 72 : 112} />
      </span>
      <span className="space-y-1.5">
        <span className={cn('block font-semibold tracking-tight text-text-primary', compact ? 'text-[17px]' : 'text-[20px]')}>
          {hot ? 'Drop it' : title}
        </span>
        {hint && <span className="block text-[15px] text-text-secondary">{hint}</span>}
      </span>
      <input
        ref={input}
        type="file"
        accept={accept}
        multiple={multiple}
        className="sr-only"
        tabIndex={-1}
        onChange={(e) => { take(e.target.files); e.target.value = '' }}
      />
    </button>
  )
}
