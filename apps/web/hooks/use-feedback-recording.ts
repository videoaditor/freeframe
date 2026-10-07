'use client'

import { useEffect, useRef, useState } from 'react'
import { api } from '@/lib/api'

const MAX_BYTES = 8 * 1024 * 1024
// Leave a second for recorder/container tail before the server’s 120s ceiling.
const MAX_SECONDS = 119

type Clip = { id: string; blob: Blob; url: string }
type Phase = 'idle' | 'starting' | 'recording' | 'uploading' | 'transcribing'

export function useFeedbackRecording(onTranscript: (text: string) => void) {
  const [phase, setPhase] = useState<Phase>('idle')
  const [clip, setClip] = useState<Clip | null>(null)
  const [recordingId, setRecordingId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [note, setNote] = useState('')
  const [seconds, setSeconds] = useState(0)
  const [level, setLevel] = useState(0)
  const meter = useRef<{ context: AudioContext; source: MediaStreamAudioSourceNode; timer: ReturnType<typeof setInterval> } | null>(null)
  const recorder = useRef<MediaRecorder | null>(null)
  const stream = useRef<MediaStream | null>(null)
  const timer = useRef<ReturnType<typeof setInterval> | null>(null)
  const clipRef = useRef<Clip | null>(null)
  const mounted = useRef(true)
  const generation = useRef(0)
  const working = useRef(false)
  const transcriptCallback = useRef(onTranscript)
  transcriptCallback.current = onTranscript

  function releaseMic() {
    if (meter.current) {
      clearInterval(meter.current.timer)
      meter.current.source.disconnect()
      void meter.current.context.close().catch(() => {})
      meter.current = null
    }
    if (mounted.current) setLevel(0)
    if (timer.current) clearInterval(timer.current)
    timer.current = null
    stream.current?.getTracks().forEach(track => track.stop())
    stream.current = null
  }

  function stop() {
    generation.current++
    if (recorder.current?.state === 'recording') recorder.current.stop()
    else if (phase === 'starting') { working.current = false; setPhase('idle') }
    releaseMic()
  }

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      generation.current++
      if (recorder.current?.state === 'recording') recorder.current.stop()
      releaseMic()
      if (clipRef.current) URL.revokeObjectURL(clipRef.current.url)
    }
  }, [])

  async function save(original: Clip) {
    working.current = true
    if (mounted.current) { setPhase('uploading'); setError(''); setNote('') }
    try {
      const form = new FormData()
      form.append('recording_id', original.id)
      form.append('file', original.blob, 'feedback-recording')
      const saved = await api.upload<{ id: string }>('/product-feedback/recordings', form)
      if (mounted.current) { setRecordingId(saved.id); setPhase('transcribing'); setNote('Audio saved. Turning it into text…') }
      try {
        const result = await api.post<{ status: string; text: string | null }>(`/product-feedback/recordings/${saved.id}/transcribe`, {})
        if (mounted.current) {
          if (result.status === 'transcribed' && result.text) {
            transcriptCallback.current(result.text)
            setNote('Audio saved. Edit the text, then send.')
          } else setNote('Audio saved. Dictation is unavailable; you can still send your voice note.')
        }
      } catch {
        if (mounted.current) setNote('Audio saved. Dictation failed; you can still send your voice note.')
      }
    } catch {
      if (mounted.current) setError('Audio not saved yet. Retry or remove it to send your text.')
    } finally {
      working.current = false
      if (mounted.current) setPhase('idle')
    }
  }

  async function start() {
    if (working.current || clipRef.current) return
    setError(''); setNote(''); setSeconds(0)
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setError('This browser cannot record audio. You can still type below.')
      return
    }
    working.current = true
    setPhase('starting')
    const currentGeneration = ++generation.current
    try {
      const input = await navigator.mediaDevices.getUserMedia({ audio: true })
      if (!mounted.current || generation.current !== currentGeneration) {
        input.getTracks().forEach(track => track.stop())
        return
      }
      stream.current = input
      const mimeType = ['audio/webm;codecs=opus', 'audio/mp4', 'audio/ogg;codecs=opus', 'audio/webm']
        .find(type => MediaRecorder.isTypeSupported(type))
      const active = new MediaRecorder(input, mimeType ? { mimeType } : undefined)
      recorder.current = active
      const chunks: Blob[] = []
      let bytes = 0
      active.ondataavailable = event => {
        if (event.data.size) { chunks.push(event.data); bytes += event.data.size }
        if (bytes > MAX_BYTES && active.state === 'recording') active.stop()
      }
      active.onstop = () => {
        releaseMic()
        recorder.current = null
        const blob = new Blob(chunks, { type: active.mimeType || chunks[0]?.type || 'audio/webm' })
        if (!blob.size || blob.size > MAX_BYTES) {
          working.current = false
          if (mounted.current) { setPhase('idle'); setError(blob.size ? 'Recording too large. Please try a shorter voice note.' : 'No audio captured. Please try again.') }
          return
        }
        const original = { id: crypto.randomUUID(), blob, url: mounted.current ? URL.createObjectURL(blob) : '' }
        clipRef.current = original
        if (mounted.current) setClip(original)
        void save(original)
      }
      active.onerror = () => {
        if (active.state === 'recording') active.stop()
        releaseMic()
      }
      // Decorative only: recording still works if Web Audio is unavailable.
      if (typeof AudioContext !== 'undefined') {
        let context: AudioContext | undefined
        try {
          context = new AudioContext()
          const analyser = context.createAnalyser()
          analyser.fftSize = 256
          const source = context.createMediaStreamSource(input)
          source.connect(analyser)
          const samples = new Uint8Array(analyser.fftSize)
          const meterTimer = setInterval(() => {
            analyser.getByteTimeDomainData(samples)
            const rms = Math.sqrt(samples.reduce((sum, value) => sum + ((value - 128) / 128) ** 2, 0) / samples.length)
            if (mounted.current) setLevel(Math.min(1, rms * 5))
          }, 80)
          meter.current = { context, source, timer: meterTimer }
          void context.resume().catch(() => {})
        } catch { if (context) void context.close().catch(() => {}) }
      }
      active.start(1000)
      setPhase('recording')
      const started = Date.now()
      timer.current = setInterval(() => {
        const elapsed = Math.floor((Date.now() - started) / 1000)
        if (mounted.current) setSeconds(Math.min(elapsed, MAX_SECONDS))
        if (elapsed >= MAX_SECONDS && active.state === 'recording') active.stop()
      }, 250)
    } catch {
      if (generation.current !== currentGeneration) return
      releaseMic()
      working.current = false
      if (mounted.current) {
        setPhase('idle'); setError('Microphone unavailable. Allow microphone access or type your feedback.')
      }
    }
  }

  function reset() {
    if (working.current) return
    if (clipRef.current) URL.revokeObjectURL(clipRef.current.url)
    clipRef.current = null
    setClip(null); setRecordingId(null); setError(''); setNote(''); setSeconds(0)
  }

  return {
    start, stop, reset, retry: () => clipRef.current && !working.current ? save(clipRef.current) : Promise.resolve(),
    phase, seconds, level, error, note, recordingId, audioUrl: clip?.url,
    busy: phase !== 'idle', unsaved: Boolean(clip && !recordingId),
  }
}
