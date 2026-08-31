/**
 * components/UploadCard.jsx — Drag-and-drop / file-picker upload widget.
 *
 * Phase 1: Full implementation.
 *   - Accepts MP4, MP3, WAV, M4A, MOV
 *   - Drag-and-drop and click-to-browse
 *   - Client-side type + size validation (max 500 MB)
 *   - XHR upload with real-time progress bar
 *   - Calls uploadMeeting() from services/api.js
 *   - Calls onSuccess(data) with the API response on completion
 *   - Calls onError(message) on failure
 */

import { useState, useRef, useCallback } from 'react'
import { uploadMeeting } from '../services/api'

const ACCEPTED_TYPES = ['.mp4', '.mp3', '.wav', '.m4a', '.mov']
const ACCEPTED_MIME = [
  'video/mp4', 'video/quicktime',
  'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/x-wav',
  'audio/wave', 'audio/x-m4a', 'audio/mp4',
]
const MAX_MB = 500

/** Format seconds into mm:ss or hh:mm:ss */
function fmtDuration(secs) {
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  const s = Math.floor(secs % 60)
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${m}:${String(s).padStart(2, '0')}`
}

/** Format bytes to human-readable string */
function fmtBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`
}

export default function UploadCard({ onSuccess, onError }) {
  const [dragOver, setDragOver] = useState(false)
  const [status, setStatus] = useState('idle')  // idle | uploading | processing | done | error
  const [progress, setProgress] = useState(0)
  const [selectedFile, setSelectedFile] = useState(null)
  const [errorMsg, setErrorMsg] = useState('')
  const inputRef = useRef(null)

  const validateFile = useCallback((file) => {
    if (!file) return 'No file selected.'
    const ext = '.' + file.name.split('.').pop().toLowerCase()
    const mimeOk = ACCEPTED_MIME.includes(file.type)
    const extOk = ACCEPTED_TYPES.includes(ext)
    if (!mimeOk && !extOk) {
      return `Unsupported file type "${ext}". Please upload: ${ACCEPTED_TYPES.join(', ')}`
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      return `File too large (${fmtBytes(file.size)}). Maximum is ${MAX_MB} MB.`
    }
    return null  // valid
  }, [])

  const handleFile = useCallback(async (file) => {
    const err = validateFile(file)
    if (err) {
      setErrorMsg(err)
      setStatus('error')
      onError?.(err)
      return
    }

    setSelectedFile(file)
    setErrorMsg('')
    setStatus('uploading')
    setProgress(0)

    try {
      const data = await uploadMeeting(file, (pct) => {
        setProgress(pct)
        if (pct === 100) setStatus('processing')  // backend is now running Whisper
      })
      setStatus('done')
      onSuccess?.(data)
    } catch (e) {
      const msg = e.message ?? 'Upload failed. Please try again.'
      setErrorMsg(msg)
      setStatus('error')
      onError?.(msg)
    }
  }, [validateFile, onSuccess, onError])

  // ── Drag handlers ────────────────────────────────────────────────────────
  const onDragEnter = (e) => { e.preventDefault(); setDragOver(true) }
  const onDragLeave = (e) => { e.preventDefault(); setDragOver(false) }
  const onDragOver  = (e) => { e.preventDefault() }
  const onDrop      = (e) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleFile(file)
  }
  const onInputChange = (e) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
    e.target.value = ''  // reset so same file can be re-selected
  }

  const reset = () => {
    setStatus('idle')
    setProgress(0)
    setSelectedFile(null)
    setErrorMsg('')
  }

  // ── Render ───────────────────────────────────────────────────────────────
  const isIdle       = status === 'idle'
  const isUploading  = status === 'uploading'
  const isProcessing = status === 'processing'
  const isDone       = status === 'done'
  const isError      = status === 'error'
  const isBusy       = isUploading || isProcessing

  return (
    <div className="w-full max-w-2xl mx-auto animate-fade-up">
      {/* Drop zone */}
      <div
        role="button"
        tabIndex={isBusy ? -1 : 0}
        aria-label="Upload meeting recording — click or drag a file here"
        onClick={() => !isBusy && inputRef.current?.click()}
        onKeyDown={(e) => e.key === 'Enter' && !isBusy && inputRef.current?.click()}
        onDragEnter={onDragEnter}
        onDragLeave={onDragLeave}
        onDragOver={onDragOver}
        onDrop={!isBusy ? onDrop : undefined}
        style={{
          border: `2px dashed ${
            dragOver        ? 'var(--clr-primary)'  :
            isError         ? 'var(--clr-error)'    :
            isDone          ? 'var(--clr-success)'  :
            isBusy          ? 'var(--clr-border-2)' :
                              'var(--clr-border)'
          }`,
          borderRadius: 'var(--radius-xl)',
          background: dragOver
            ? 'rgba(99,102,241,0.08)'
            : 'var(--grad-card)',
          padding: '40px 32px',
          cursor: isBusy ? 'default' : 'pointer',
          transition: 'all var(--transition)',
          boxShadow: dragOver ? 'var(--glow-primary)' : 'none',
        }}
      >
        {/* Hidden file input */}
        <input
          ref={inputRef}
          type="file"
          id="file-input"
          accept={ACCEPTED_TYPES.join(',')}
          className="hidden"
          onChange={onInputChange}
          disabled={isBusy}
        />

        {/* Icon area */}
        <div className="flex flex-col items-center gap-5 text-center">
          {/* State icon */}
          <div style={{
            width: 72, height: 72,
            borderRadius: '50%',
            background: isDone    ? 'rgba(16,185,129,0.15)' :
                        isError   ? 'rgba(239,68,68,0.15)'  :
                        isBusy    ? 'rgba(99,102,241,0.15)' :
                                    'rgba(99,102,241,0.10)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 32,
            border: `1px solid ${isDone ? 'var(--clr-success)' : isError ? 'var(--clr-error)' : 'var(--clr-border)'}`,
            animation: isBusy ? 'pulse-ring 1.5s infinite' : 'none',
          }}>
            {isDone       ? '✅' :
             isError      ? '❌' :
             isProcessing ? <SpinnerIcon /> :
             isUploading  ? '📤' :
                            <UploadIcon />}
          </div>

          {/* Label */}
          <div>
            {isIdle && (
              <>
                <p style={{ fontSize: 18, fontWeight: 600, color: 'var(--clr-text)', marginBottom: 6 }}>
                  Drop your meeting recording here
                </p>
                <p style={{ fontSize: 13, color: 'var(--clr-text-muted)' }}>
                  or <span style={{ color: 'var(--clr-primary)', fontWeight: 600 }}>browse files</span>
                  {' '}— {ACCEPTED_TYPES.join(', ')} • max {MAX_MB} MB
                </p>
              </>
            )}

            {isUploading && selectedFile && (
              <>
                <p style={{ fontSize: 16, fontWeight: 600, color: 'var(--clr-text)', marginBottom: 4 }}>
                  Uploading {selectedFile.name}
                </p>
                <p style={{ fontSize: 13, color: 'var(--clr-text-muted)', marginBottom: 16 }}>
                  {fmtBytes(selectedFile.size)}
                </p>
                <ProgressBar pct={progress} label={`${progress}%`} />
              </>
            )}

            {isProcessing && (
              <>
                <p style={{ fontSize: 16, fontWeight: 600, color: 'var(--clr-primary)', marginBottom: 4 }}>
                  Transcribing with Faster-Whisper…
                </p>
                <p style={{ fontSize: 13, color: 'var(--clr-text-muted)' }}>
                  This may take a minute for longer recordings.
                </p>
              </>
            )}

            {isDone && (
              <p style={{ fontSize: 16, fontWeight: 600, color: 'var(--clr-success)' }}>
                Transcript ready! Redirecting…
              </p>
            )}

            {isError && (
              <>
                <p style={{ fontSize: 16, fontWeight: 600, color: 'var(--clr-error)', marginBottom: 6 }}>
                  {errorMsg || 'Something went wrong.'}
                </p>
                <button
                  id="upload-retry-btn"
                  onClick={(e) => { e.stopPropagation(); reset() }}
                  style={{
                    marginTop: 8,
                    padding: '8px 20px',
                    borderRadius: 'var(--radius-sm)',
                    background: 'rgba(239,68,68,0.15)',
                    border: '1px solid var(--clr-error)',
                    color: 'var(--clr-error)',
                    fontWeight: 600, fontSize: 13,
                    cursor: 'pointer',
                  }}
                >
                  Try again
                </button>
              </>
            )}
          </div>

          {/* Format chips (only in idle) */}
          {isIdle && (
            <div className="flex flex-wrap gap-2 justify-center" style={{ marginTop: 4 }}>
              {ACCEPTED_TYPES.map(ext => (
                <span
                  key={ext}
                  style={{
                    padding: '3px 10px',
                    borderRadius: 'var(--radius-sm)',
                    background: 'rgba(99,102,241,0.12)',
                    border: '1px solid var(--clr-border)',
                    color: 'var(--clr-primary-h)',
                    fontSize: 11,
                    fontWeight: 600,
                    letterSpacing: '0.05em',
                    textTransform: 'uppercase',
                  }}
                >
                  {ext.slice(1)}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Small sub-components ─────────────────────────────────────────────────────

function ProgressBar({ pct, label }) {
  return (
    <div style={{ width: '100%', maxWidth: 320, margin: '0 auto' }}>
      <div className="progress-bar">
        <div className="progress-bar__fill" style={{ width: `${pct}%` }} />
      </div>
      <p style={{ fontSize: 12, color: 'var(--clr-text-muted)', marginTop: 6 }}>{label}</p>
    </div>
  )
}

function UploadIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--clr-primary)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
      <polyline points="17 8 12 3 7 8"/>
      <line x1="12" y1="3" x2="12" y2="15"/>
    </svg>
  )
}

function SpinnerIcon() {
  return (
    <svg className="animate-spin" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--clr-primary)" strokeWidth="2.5" strokeLinecap="round">
      <circle cx="12" cy="12" r="10" strokeOpacity="0.2"/>
      <path d="M12 2a10 10 0 010 20" stroke="var(--clr-primary)"/>
    </svg>
  )
}
