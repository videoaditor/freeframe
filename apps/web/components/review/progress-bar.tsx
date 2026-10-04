'use client'

import React, { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import Hls from 'hls.js'
import { cn, formatTimecode } from '@/lib/utils'
import { useReviewStore } from '@/stores/review-store'
import type { Comment } from '@/types'

// ─── Avatar helpers ───────────────────────────────────────────────────────────

const AVATAR_COLORS = [
  '#E67E22', '#E74C3C', '#9B59B6', '#3498DB', '#1ABC9C',
  '#2ECC71', '#F39C12', '#D35400', '#8E44AD', '#2980B9',
]

export function getAvatarColor(name: string): string {
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash)
  }
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length]
}

export function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/)
  if (parts.length === 1) return parts[0].charAt(0).toUpperCase()
  return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase()
}

// ─── Types ────────────────────────────────────────────────────────────────────

interface ProgressBarProps {
  currentTime: number
  duration: number
  buffered?: number
  comments?: Comment[]
  videoRef?: React.RefObject<HTMLVideoElement | null>
  streamUrl?: string | null
  onSeek: (time: number) => void
  className?: string
}

// ─── Frame Preview Hook ───────────────────────────────────────────────────────

function useFramePreview(streamUrl: string | null | undefined) {
  const previewVideoRef = useRef<HTMLVideoElement | null>(null)
  const previewHlsRef = useRef<Hls | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const seekResolveRef = useRef<(() => void) | null>(null)
  const readyRef = useRef(false)
  const [previewImage, setPreviewImage] = useState<string | null>(null)

  // Initialize hidden preview video + HLS
  useEffect(() => {
    if (!streamUrl) return

    const video = document.createElement('video')
    video.muted = true
    video.playsInline = true
    video.preload = 'auto'
    video.crossOrigin = 'anonymous'
    video.style.display = 'none'
    document.body.appendChild(video)
    previewVideoRef.current = video

    const canvas = document.createElement('canvas')
    canvas.width = 160
    canvas.height = 90
    canvasRef.current = canvas

    const isHls = streamUrl.includes('.m3u8')

    const onReady = () => {
      readyRef.current = true
    }

    video.addEventListener('loadeddata', onReady)

    video.addEventListener('seeked', () => {
      // Capture frame
      try {
        const ctx = canvas.getContext('2d')
        if (ctx && video.videoWidth > 0) {
          const aspectRatio = video.videoWidth / video.videoHeight
          const w = 160
          const h = Math.round(w / aspectRatio)
          canvas.width = w
          canvas.height = h
          ctx.drawImage(video, 0, 0, w, h)
          setPreviewImage(canvas.toDataURL('image/jpeg', 0.7))
        }
      } catch {
        // CORS — silently fail
      }
      seekResolveRef.current?.()
      seekResolveRef.current = null
    })

    if (isHls && Hls.isSupported()) {
      const hls = new Hls({
        enableWorker: false,
        maxBufferLength: 1,
        maxMaxBufferLength: 2,
        maxBufferSize: 0.5 * 1024 * 1024, // 500KB — minimal buffering
      })
      previewHlsRef.current = hls
      hls.loadSource(streamUrl)
      hls.attachMedia(video)
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = streamUrl
    } else {
      video.src = streamUrl
    }

    return () => {
      readyRef.current = false
      if (previewHlsRef.current) {
        previewHlsRef.current.destroy()
        previewHlsRef.current = null
      }
      video.removeEventListener('loadeddata', onReady)
      video.src = ''
      video.remove()
      previewVideoRef.current = null
      canvasRef.current = null
      setPreviewImage(null)
    }
  }, [streamUrl])

  const seekPreview = useCallback((time: number) => {
    const video = previewVideoRef.current
    if (!video || !readyRef.current) return
    // Debounce: if already seeking, skip
    if (seekResolveRef.current) return
    seekResolveRef.current = () => {}
    video.currentTime = Math.max(0, time)
  }, [])

  const clearPreview = useCallback(() => {
    setPreviewImage(null)
  }, [])

  return { previewImage, seekPreview, clearPreview }
}

// ─── Comment Marker ──────────────────────────────────────────────────────────

interface CommentMarkerProps {
  comment: Comment
  index: number
  leftPercent: number
  authorName: string
  initials: string
  color: string
  isHovered: boolean
  isFocused: boolean
  onHover: () => void
  onLeave: () => void
  onSeek: (time: number) => void
}

function CommentMarker({
  comment,
  index,
  leftPercent,
  authorName,
  initials,
  color,
  isHovered,
  isFocused,
  onHover,
  onLeave,
  onSeek,
}: CommentMarkerProps) {
  const markerRef = useRef<HTMLDivElement>(null)
  const setFocusedCommentId = useReviewStore((s) => s.setFocusedCommentId)
  const setActiveAnnotation = useReviewStore((s) => s.setActiveAnnotation)
  const seekTo = useReviewStore((s) => s.seekTo)
  const [tooltipPos, setTooltipPos] = useState<{ left: number; top: number } | null>(null)

  // Recalculate tooltip position when hovered to avoid viewport clipping
  useEffect(() => {
    if (!isHovered || !markerRef.current) {
      setTooltipPos(null)
      return
    }
    const rect = markerRef.current.getBoundingClientRect()
    const tooltipWidth = 240
    let left = rect.left + rect.width / 2 - tooltipWidth / 2
    if (left < 8) left = 8
    if (left + tooltipWidth > window.innerWidth - 8) left = window.innerWidth - 8 - tooltipWidth
    setTooltipPos({ left, top: rect.top - 8 })
  }, [isHovered])

  const handleClick = useCallback(() => {
    if (comment.timecode_start !== null) {
      seekTo(comment.timecode_start, true)
    }
    setFocusedCommentId(comment.id)
    if ((comment as any).annotation?.drawing_data) {
      setActiveAnnotation((comment as any).annotation.drawing_data)
    } else {
      setActiveAnnotation(null)
    }
  }, [comment, seekTo, setFocusedCommentId, setActiveAnnotation])

  return (
    <div
      ref={markerRef}
      className="absolute top-0 -translate-x-1/2 cursor-pointer"
      style={{ left: `${leftPercent}%` }}
      onMouseEnter={onHover}
      onMouseLeave={onLeave}
      onClick={handleClick}
    >
      {/* Avatar dot */}
      <div
        className={cn(
          'w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold text-white shadow-md border-2 transition-transform hover:scale-110',
          isFocused ? 'border-accent scale-125 ring-2 ring-accent/40' : 'border-bg-primary',
        )}
        style={{ backgroundColor: color }}
      >
        {initials}
      </div>

      {/* Tooltip — portaled to document.body to escape all overflow */}
      {isHovered && tooltipPos && createPortal(
        <div
          style={{
            position: 'fixed',
            left: tooltipPos.left,
            top: tooltipPos.top,
            width: 240,
            transform: 'translateY(-100%)',
            zIndex: 9999,
            pointerEvents: 'none',
          }}
        >
          <div className="bg-[#1e1e22] border border-white/10 rounded-lg shadow-2xl p-3">
            <div className="flex items-center gap-2 mb-1.5">
              <div
                className="w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold text-white shrink-0"
                style={{ backgroundColor: color }}
              >
                {initials}
              </div>
              <span className="text-xs font-medium text-white truncate">{authorName}</span>
              {comment.timecode_start !== null && (
                <span className="ml-auto text-[10px] font-mono text-indigo-400 bg-indigo-500/10 px-1.5 py-0.5 rounded">
                  {formatTimecode(comment.timecode_start)}
                </span>
              )}
            </div>
            <p className="text-xs text-text-secondary line-clamp-2 leading-relaxed">
              {comment.body}
            </p>
          </div>
          {/* Arrow */}
          <div className="flex justify-center">
            <div className="w-2 h-2 bg-[#1e1e22] border-b border-r border-white/10 rotate-45 -mt-1" />
          </div>
        </div>,
        document.body,
      )}
    </div>
  )
}

// ─── Component ────────────────────────────────────────────────────────────────

export function ProgressBar({
  currentTime,
  duration,
  buffered = 0,
  comments = [],
  streamUrl,
  onSeek,
  className,
}: ProgressBarProps) {
  const trackRef = useRef<HTMLDivElement>(null)
  const [hoverTime, setHoverTime] = useState<number | null>(null)
  const [hoverX, setHoverX] = useState(0)
  const [hoveredCommentId, setHoveredCommentId] = useState<string | null>(null)
  const focusedCommentId = useReviewStore((s) => s.focusedCommentId)

  const { previewImage, seekPreview, clearPreview } = useFramePreview(streamUrl)
  const safeDuration = Number.isFinite(duration) && duration > 0 ? duration : 0
  const safeTime = Number.isFinite(currentTime) ? Math.max(0, Math.min(safeDuration, currentTime)) : 0

  const timeToPercent = useCallback(
    (time: number): number => {
      if (!duration) return 0
      return Math.max(0, Math.min(100, (time / duration) * 100))
    },
    [duration],
  )

  const getTimeFromEvent = useCallback(
    (clientX: number): number => {
      const track = trackRef.current
      if (!track || !duration) return 0
      const rect = track.getBoundingClientRect()
      const ratio = Math.max(0, Math.min(1, (clientX - rect.left - 10) / Math.max(1, rect.width - 20)))
      return ratio * duration
    },
    [duration],
  )

  const handlePointerMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (e.pointerType !== 'mouse') {
        setHoverTime(null)
        clearPreview()
        return
      }
      const time = getTimeFromEvent(e.clientX)
      setHoverTime(time)
      const track = trackRef.current
      if (track) {
        const rect = track.getBoundingClientRect()
        setHoverX(e.clientX - rect.left)
      }
      seekPreview(time)
    },
    [getTimeFromEvent, seekPreview, clearPreview],
  )

  const handleMouseLeave = useCallback(() => {
    setHoverTime(null)
    clearPreview()
  }, [clearPreview])

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (!safeDuration) return
    let next: number
    switch (event.key) {
      case 'ArrowRight': case 'ArrowUp': next = safeTime + 0.1; break
      case 'ArrowLeft': case 'ArrowDown': next = safeTime - 0.1; break
      case 'PageUp': next = safeTime + 1; break
      case 'PageDown': next = safeTime - 1; break
      case 'Home': next = 0; break
      case 'End': next = safeDuration; break
      default: return
    }
    event.preventDefault()
    onSeek(Math.max(0, Math.min(safeDuration, next)))
  }

  // Separate timecoded comments
  const pointMarkers = comments.filter(
    (c) => c.timecode_start !== null && c.timecode_end === null && !c.resolved,
  )
  const rangeMarkers = comments.filter(
    (c) => c.timecode_start !== null && c.timecode_end !== null && !c.resolved,
  )

  const playPercent = timeToPercent(currentTime)
  const bufferedPercent = timeToPercent(buffered)

  return (
    <div className={cn('relative flex flex-col w-full group/progress px-4 pb-2', className)}>
      {/* Track area */}
      <div
        ref={trackRef}
        className="relative w-full h-12 focus-within:ring-2 focus-within:ring-accent/60 rounded-md"
        onPointerMove={handlePointerMove}
        onPointerLeave={handleMouseLeave}
      >
        <input
          type="range"
          aria-label="Video timeline"
          aria-valuetext={`${Number(safeTime.toFixed(1))} of ${Number(safeDuration.toFixed(1))} seconds`}
          min={0}
          max={safeDuration}
          step="any"
          value={safeTime}
          disabled={!safeDuration}
          onChange={(event) => onSeek(Number(event.currentTarget.value))}
          onKeyDown={handleKeyDown}
          onBlur={handleMouseLeave}
          className="absolute inset-0 z-20 w-full h-12 m-0 appearance-none bg-transparent cursor-pointer touch-none disabled:cursor-default focus:outline-none [&::-webkit-slider-runnable-track]:h-5 [&::-webkit-slider-runnable-track]:bg-transparent [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-accent [&::-webkit-slider-thumb]:shadow-md [&::-moz-range-track]:h-5 [&::-moz-range-track]:bg-transparent [&::-moz-range-thumb]:w-5 [&::-moz-range-thumb]:h-5 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:bg-accent [&::-moz-range-thumb]:shadow-md"
        />
        <div className="absolute inset-x-2.5 top-1/2 -translate-y-1/2 h-2 bg-border rounded-full pointer-events-none">
        {/* Buffered range */}
        <div
          className="absolute inset-y-0 left-0 bg-border-secondary rounded-full"
          style={{ width: `${bufferedPercent}%` }}
        />

        {/* Time-range comment spans */}
        {rangeMarkers.map((c) => {
          if (c.timecode_start === null || c.timecode_end === null) return null
          const left = timeToPercent(c.timecode_start)
          const right = timeToPercent(c.timecode_end)
          return (
            <div
              key={c.id}
              className="absolute inset-y-0 bg-yellow-400/40 rounded-full pointer-events-none"
              style={{
                left: `${left}%`,
                width: `${right - left}%`,
              }}
            />
          )
        })}

        {/* Playback progress */}
        <div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{
            width: `${playPercent}%`,
            background: 'linear-gradient(90deg, #6366f1, #818cf8)',
          }}
        />

        </div>
      </div>
      {safeDuration > 0 && (
        <div className="flex justify-between gap-2 text-xs leading-4 tabular-nums text-text-secondary" aria-hidden="true">
          {Array.from({ length: 6 }, (_, index) => (
            <span key={index}>{Number((safeDuration * index / 5).toFixed(1))}s</span>
          ))}
        </div>
      )}

      {/* Comment markers row — below the progress bar */}
      {pointMarkers.length > 0 && (
        <div className="relative h-6 mx-2.5 mt-1">
          {pointMarkers.map((c, idx) => {
            if (c.timecode_start === null) return null
            const left = timeToPercent(c.timecode_start)
            const authorName = c.author?.name ?? c.guest_author?.name ?? 'Unknown'
            const initials = getInitials(authorName)
            const color = getAvatarColor(authorName)
            const isHovered = hoveredCommentId === c.id

            return (
              <CommentMarker
                key={c.id}
                comment={c}
                index={idx}
                leftPercent={left}
                authorName={authorName}
                initials={initials}
                color={color}
                isHovered={isHovered}
                isFocused={focusedCommentId === c.id}
                onHover={() => setHoveredCommentId(c.id)}
                onLeave={() => setHoveredCommentId(null)}
                onSeek={onSeek}
              />
            )
          })}
        </div>
      )}

      {/* Frame preview + time tooltip on bar hover */}
      {hoverTime !== null && (
        <div
          className="absolute -top-2 z-30 pointer-events-none"
          style={{ left: hoverX, transform: 'translateX(-50%) translateY(-100%)' }}
        >
          {/* Frame preview */}
          {previewImage && (
            <div className="mb-1 rounded-md overflow-hidden border border-white/15 shadow-2xl">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={previewImage} alt="" className="w-40 object-contain bg-black" />
            </div>
          )}
          {/* Time label */}
          <div className="flex justify-center">
            <span className="bg-black/90 text-white text-[11px] font-mono px-2 py-0.5 rounded-md">
              {formatTimecode(hoverTime)}
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
