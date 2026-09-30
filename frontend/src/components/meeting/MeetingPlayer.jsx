import { useEffect, useMemo, useRef, useState } from 'react'
import { getMediaUrl } from '../../services/api'
import { findActiveSegment, formatClock } from './playback'

const RATES = [0.75, 1, 1.25, 1.5, 2]

export default function MeetingPlayer({ fileId, meeting, onActiveSegmentChange, seekRequest, onSeekHandled }) {
  const audioRef = useRef(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(Number.isFinite(meeting?.duration) ? meeting.duration : 0)
  const [playbackRate, setPlaybackRate] = useState(1)
  const [volume, setVolume] = useState(1)
  const [lastSegmentId, setLastSegmentId] = useState(null)

  const segments = useMemo(() => Array.isArray(meeting?.segments) ? meeting.segments : [], [meeting])
  const mediaUrl = fileId ? getMediaUrl(fileId) : ''
  const mimeType = useMemo(() => {
    const ext = (meeting?.filename || '').split('.').pop()?.toLowerCase() || ''
    if (['mp4', 'mov', 'avi'].includes(ext)) return 'video'
    return 'audio'
  }, [meeting])

  useEffect(() => {
    const media = audioRef.current
    if (!media) return
    media.playbackRate = playbackRate
    media.volume = volume
  }, [playbackRate, volume])

  useEffect(() => {
    const media = audioRef.current
    if (!media || !Number.isFinite(seekRequest?.seconds)) return
    const next = Math.min(Math.max(seekRequest.seconds, 0), Number.isFinite(media.duration) && media.duration > 0 ? media.duration : Number.POSITIVE_INFINITY)
    media.currentTime = next
    setCurrentTime(next)
    if (seekRequest.play) {
      media.play().catch(() => setIsPlaying(false))
      setIsPlaying(true)
    }
    onSeekHandled?.()
  }, [seekRequest, onSeekHandled])

  useEffect(() => {
    const active = findActiveSegment(segments, currentTime)
    const nextId = active ? (active.id ?? active.__index ?? null) : null
    if (nextId !== lastSegmentId) {
      setLastSegmentId(nextId)
      onActiveSegmentChange?.(nextId)
    }
  }, [segments, currentTime, lastSegmentId, onActiveSegmentChange])

  useEffect(() => {
    const media = audioRef.current
    if (!media) return
    const handleTimeUpdate = () => {
      setCurrentTime(media.currentTime || 0)
      if (Number.isFinite(media.duration) && media.duration > 0) setDuration(media.duration)
    }
    const handleLoadedMetadata = () => {
      setDuration(Number.isFinite(media.duration) && media.duration > 0 ? media.duration : Number.isFinite(meeting?.duration) ? meeting.duration : 0)
      setCurrentTime(media.currentTime || 0)
    }
    const handlePlay = () => setIsPlaying(true)
    const handlePause = () => setIsPlaying(false)
    const handleEnded = () => setIsPlaying(false)

    media.addEventListener('timeupdate', handleTimeUpdate)
    media.addEventListener('loadedmetadata', handleLoadedMetadata)
    media.addEventListener('play', handlePlay)
    media.addEventListener('pause', handlePause)
    media.addEventListener('ended', handleEnded)

    return () => {
      media.removeEventListener('timeupdate', handleTimeUpdate)
      media.removeEventListener('loadedmetadata', handleLoadedMetadata)
      media.removeEventListener('play', handlePlay)
      media.removeEventListener('pause', handlePause)
      media.removeEventListener('ended', handleEnded)
    }
  }, [meeting])

  const togglePlay = async () => {
    const media = audioRef.current
    if (!media) return
    try {
      if (media.paused) {
        await media.play()
      } else {
        media.pause()
      }
    } catch {
      setIsPlaying(false)
    }
  }

  const skipBy = (seconds) => {
    const media = audioRef.current
    if (!media) return
    media.currentTime = Math.min(Math.max((media.currentTime || 0) + seconds, 0), media.duration || 0)
    setCurrentTime(media.currentTime)
    if (!media.paused && isPlaying) {
      media.play().catch(() => {})
    }
  }

  const handleSeek = (value) => {
    const media = audioRef.current
    if (!media) return
    media.currentTime = Number(value)
    setCurrentTime(Number(value))
  }

  return (
    <div id="meeting-player" className="mi-player-shell">
      <div className="mi-player">
        <div className="mi-player-media" aria-label="Meeting media player">
          {mimeType === 'video' ? (
            <video ref={audioRef} src={mediaUrl} controls={false} preload="metadata" playsInline />
          ) : (
            <audio ref={audioRef} src={mediaUrl} controls={false} preload="metadata" />
          )}
        </div>
        <div className="mi-player-controls">
          <button type="button" className="mi-player-button" aria-label="Play or pause meeting" onClick={togglePlay}>{isPlaying ? 'Pause' : 'Play'}</button>
          <button type="button" className="mi-player-button" aria-label="Skip back 10 seconds" onClick={() => skipBy(-10)}>-10s</button>
          <button type="button" className="mi-player-button" aria-label="Skip forward 10 seconds" onClick={() => skipBy(10)}>+10s</button>
          <span className="mi-player-time">{formatClock(currentTime)} / {formatClock(duration)}</span>
          <div className="mi-player-seek">
            <input aria-label="Seek meeting position" type="range" min="0" max={Math.max(duration, 0) || 1} value={Math.min(currentTime, Math.max(duration, 0) || 0)} onChange={(event) => handleSeek(event.target.value)} />
          </div>
          <label className="mi-player-rate">
            <span>Speed</span>
            <select aria-label="Playback speed" value={String(playbackRate)} onChange={(event) => setPlaybackRate(Number(event.target.value))}>
              {RATES.map((rate) => <option key={rate} value={String(rate)}>{rate.toFixed(rate % 1 === 0 ? 0 : 2)}×</option>)}
            </select>
          </label>
          <label className="mi-player-volume">
            <span>Volume</span>
            <input aria-label="Playback volume" type="range" min="0" max="1" step="0.05" value={volume} onChange={(event) => setVolume(Number(event.target.value))} />
          </label>
        </div>
      </div>
    </div>
  )
}
