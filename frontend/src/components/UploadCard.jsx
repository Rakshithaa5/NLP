/**
 * components/UploadCard.jsx -- Redesigned Evernote-style upload zone.
 * All logic preserved; only visual treatment updated to light-mode design.
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

function fmtDuration(secs) {
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  const s = Math.floor(secs % 60)
  if (h > 0) return `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`
  return `${m}:${String(s).padStart(2,'0')}`
}

function fmtBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`
}

export default function UploadCard({ onSuccess, onError }) {
  const [dragOver, setDragOver] = useState(false)
  const [status, setStatus] = useState('idle')
  const [progress, setProgress] = useState(0)
  const [selectedFile, setSelectedFile] = useState(null)
  const [errorMsg, setErrorMsg] = useState('')
  const inputRef = useRef(null)

  const validateFile = useCallback((file) => {
    if (!file) return 'No file selected.'
    const ext = '.' + file.name.split('.').pop().toLowerCase()
    const mimeOk = ACCEPTED_MIME.includes(file.type)
    const extOk = ACCEPTED_TYPES.includes(ext)
    if (!mimeOk && !extOk) return `Unsupported type "${ext}". Accepted: ${ACCEPTED_TYPES.join(', ')}`
    if (file.size > MAX_MB * 1024 * 1024) return `File too large (${fmtBytes(file.size)}). Max ${MAX_MB} MB.`
    return null
  }, [])

  const handleFile = useCallback(async (file) => {
    const err = validateFile(file)
    if (err) { setErrorMsg(err); setStatus('error'); onError?.(err); return }
    setSelectedFile(file); setErrorMsg(''); setStatus('uploading'); setProgress(0)
    try {
      const data = await uploadMeeting(file, (pct) => {
        setProgress(pct)
        if (pct === 100) setStatus('processing')
      })
      setStatus('done')
      onSuccess?.(data)
    } catch (e) {
      const msg = e.message ?? 'Upload failed. Please try again.'
      setErrorMsg(msg); setStatus('error'); onError?.(msg)
    }
  }, [validateFile, onSuccess, onError])

  const onDragEnter = (e) => { e.preventDefault(); setDragOver(true) }
  const onDragLeave = (e) => { e.preventDefault(); setDragOver(false) }
  const onDragOver  = (e) => { e.preventDefault() }
  const onDrop = (e) => { e.preventDefault(); setDragOver(false); const f = e.dataTransfer.files?.[0]; if (f) handleFile(f) }
  const onInputChange = (e) => { const f = e.target.files?.[0]; if (f) handleFile(f); e.target.value = '' }
  const reset = () => { setStatus('idle'); setProgress(0); setSelectedFile(null); setErrorMsg('') }

  const isIdle       = status === 'idle'
  const isUploading  = status === 'uploading'
  const isProcessing = status === 'processing'
  const isDone       = status === 'done'
  const isError      = status === 'error'
  const isBusy       = isUploading || isProcessing

  return (
    <div
      role="button"
      tabIndex={isBusy ? -1 : 0}
      aria-label="Upload meeting recording — click or drag a file here"
      id="upload-zone"
      onClick={() => !isBusy && inputRef.current?.click()}
      onKeyDown={(e) => e.key === 'Enter' && !isBusy && inputRef.current?.click()}
      onDragEnter={onDragEnter}
      onDragLeave={onDragLeave}
      onDragOver={onDragOver}
      onDrop={!isBusy ? onDrop : undefined}
      className={`upload-zone${dragOver ? ' drag-over' : ''}${isError ? ' error' : ''}${isDone ? ' success' : ''}${isBusy ? ' busy' : ''}`}
    >
      <input
        ref={inputRef}
        type="file"
        id="file-input"
        accept={ACCEPTED_TYPES.join(',')}
        style={{ display: 'none' }}
        onChange={onInputChange}
        disabled={isBusy}
      />

      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20 }}>

        {/* Icon */}
        <div style={{
          width: 80, height: 80, borderRadius: '50%',
          background: isDone ? 'var(--clr-primary-bg)' : isError ? '#fff5f5' : isBusy ? 'var(--clr-surface-2)' : 'var(--clr-surface-2)',
          border: `2px solid ${isDone ? 'var(--clr-primary-l)' : isError ? '#fecaca' : isBusy ? 'var(--clr-border)' : 'var(--clr-border)'}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          transition: 'all 0.3s',
        }}>
          {isDone && (
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--clr-primary)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
          )}
          {isError && (
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--clr-error)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
          )}
          {isProcessing && (
            <svg className="animate-spin" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--clr-primary)" strokeWidth="2.5" strokeLinecap="round">
              <circle cx="12" cy="12" r="10" strokeOpacity="0.15"/>
              <path d="M12 2a10 10 0 0 1 10 10"/>
            </svg>
          )}
          {isUploading && (
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--clr-primary)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
          )}
          {isIdle && (
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--clr-text-dim)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
          )}
        </div>

        {/* Content */}
        <div style={{ textAlign: 'center' }}>
          {isIdle && (
            <>
              <p style={{ fontSize: 20, fontWeight: 700, color: 'var(--clr-text)', marginBottom: 8, fontFamily: '"Plus Jakarta Sans",sans-serif' }}>
                Drop your meeting recording here
              </p>
              <p style={{ fontSize: 14, color: 'var(--clr-text-muted)' }}>
                or <span style={{ color: 'var(--clr-primary-h)', fontWeight: 600 }}>browse files</span>
                {' '}— {ACCEPTED_TYPES.join(', ')} &bull; max {MAX_MB} MB
              </p>
            </>
          )}

          {isUploading && selectedFile && (
            <>
              <p style={{ fontSize: 16, fontWeight: 600, color: 'var(--clr-text)', marginBottom: 6 }}>
                Uploading {selectedFile.name}
              </p>
              <p style={{ fontSize: 13, color: 'var(--clr-text-muted)', marginBottom: 16 }}>
                {fmtBytes(selectedFile.size)}
              </p>
              <div style={{ width: '100%', maxWidth: 320, margin: '0 auto' }}>
                <div className="progress-bar">
                  <div className="progress-bar__fill" style={{ width: `${progress}%` }} />
                </div>
                <p style={{ fontSize: 12, color: 'var(--clr-text-dim)', marginTop: 6 }}>{progress}%</p>
              </div>
            </>
          )}

          {isProcessing && (
            <>
              <p style={{ fontSize: 16, fontWeight: 600, color: 'var(--clr-primary-h)', marginBottom: 6 }}>
                Transcribing with Faster-Whisper…
              </p>
              <p style={{ fontSize: 13, color: 'var(--clr-text-muted)' }}>
                This may take a minute for longer recordings.
              </p>
            </>
          )}

          {isDone && (
            <p style={{ fontSize: 16, fontWeight: 600, color: 'var(--clr-primary-h)' }}>
              Transcript ready! Redirecting…
            </p>
          )}

          {isError && (
            <>
              <p style={{ fontSize: 15, fontWeight: 600, color: 'var(--clr-error)', marginBottom: 10 }}>
                {errorMsg || 'Something went wrong.'}
              </p>
              <button
                id="upload-retry-btn"
                onClick={(e) => { e.stopPropagation(); reset() }}
                style={{
                  padding: '8px 20px', borderRadius: 'var(--radius-sm)',
                  background: '#fff5f5', border: '1px solid var(--clr-error)',
                  color: 'var(--clr-error)', fontWeight: 600, fontSize: 13, cursor: 'pointer',
                }}
              >
                Try again
              </button>
            </>
          )}
        </div>

        {/* Format chips */}
        {isIdle && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, justifyContent: 'center' }}>
            {ACCEPTED_TYPES.map(ext => (
              <span key={ext} style={{
                padding: '3px 10px', borderRadius: 'var(--radius-sm)',
                background: 'var(--clr-surface-2)', border: '1px solid var(--clr-border)',
                color: 'var(--clr-text-dim)', fontSize: 11, fontWeight: 600,
                letterSpacing: '0.05em', textTransform: 'uppercase',
              }}>
                {ext.slice(1)}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
