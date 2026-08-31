/**
 * pages/TranscriptPreview.jsx — Raw transcript display page.
 *
 * Phase 1: Displays the Faster-Whisper transcript returned from the backend.
 *   - Shows meeting metadata (filename, duration, language)
 *   - Renders time-stamped segments
 *   - Renders full text in a copyable block
 *   - "Analyze" button (stub — Phase 2) shown but disabled
 *
 * Receives transcript data either via React Router state (from Home.jsx
 * navigate call) or fetches it by file_id from the URL param.
 */

import { useEffect, useState } from 'react'
import { useParams, useLocation, useNavigate } from 'react-router-dom'
import { getTranscript } from '../services/api'

/** Format seconds → mm:ss or hh:mm:ss */
function fmtDuration(secs) {
  if (!secs) return '—'
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  const s = Math.floor(secs % 60)
  if (h > 0) return `${h}h ${String(m).padStart(2,'0')}m ${String(s).padStart(2,'0')}s`
  return `${m}m ${String(s).padStart(2,'0')}s`
}

/** Format a segment timestamp (seconds) → [mm:ss] */
function fmtTs(secs) {
  const m = Math.floor(secs / 60)
  const s = Math.floor(secs % 60)
  return `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`
}

export default function TranscriptPreview() {
  const { fileId } = useParams()
  const location   = useLocation()
  const navigate   = useNavigate()

  // Data may come via router state (instant) or be fetched from the API
  const [data, setData]       = useState(location.state?.transcript ?? null)
  const [loading, setLoading] = useState(!data)
  const [error, setError]     = useState(null)
  const [copied, setCopied]   = useState(false)
  const [activeTab, setActiveTab] = useState('segments')  // 'segments' | 'fulltext'

  useEffect(() => {
    if (data) return  // already have it from router state
    setLoading(true)
    getTranscript(fileId)
      .then(setData)
      .catch((e) => setError(e.message ?? 'Failed to load transcript.'))
      .finally(() => setLoading(false))
  }, [fileId, data])

  const handleCopy = () => {
    if (!data?.full_text) return
    navigator.clipboard.writeText(data.full_text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  // ── Loading ──────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', gap: 16 }}>
        <div style={{
          width: 56, height: 56, borderRadius: '50%',
          border: '3px solid var(--clr-border)',
          borderTopColor: 'var(--clr-primary)',
          animation: 'spin 0.8s linear infinite',
        }} />
        <p style={{ color: 'var(--clr-text-muted)', fontSize: 14 }}>Loading transcript…</p>
      </div>
    )
  }

  // ── Error ────────────────────────────────────────────────────────────────
  if (error) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', gap: 16, padding: 24 }}>
        <div style={{ fontSize: 48 }}>⚠️</div>
        <p style={{ color: 'var(--clr-error)', fontWeight: 600 }}>{error}</p>
        <button id="transcript-back-btn" onClick={() => navigate('/')} style={btnStyle('secondary')}>
          ← Back to Upload
        </button>
      </div>
    )
  }

  // ── Main ─────────────────────────────────────────────────────────────────
  const { filename, duration, language, segments = [], full_text = '' } = data ?? {}
  const wordCount = full_text.trim().split(/\s+/).filter(Boolean).length
  const segCount  = segments.length

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '32px 24px' }} className="animate-fade-up">

      {/* Back link */}
      <button
        id="transcript-back-btn"
        onClick={() => navigate('/')}
        style={{ background: 'none', border: 'none', color: 'var(--clr-text-muted)', fontSize: 13, cursor: 'pointer', marginBottom: 24, display: 'flex', alignItems: 'center', gap: 6, padding: 0 }}
      >
        ← Back to Upload
      </button>

      {/* Header */}
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 6 }} className="gradient-text">
          Transcript Ready
        </h1>
        <p style={{ color: 'var(--clr-text-muted)', fontSize: 14 }}>
          {filename || 'Recording'}
        </p>
      </div>

      {/* Stat pills */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 28 }}>
        {[
          { label: 'Duration',  value: fmtDuration(duration), icon: '⏱' },
          { label: 'Language',  value: (language ?? '—').toUpperCase(), icon: '🌐' },
          { label: 'Segments',  value: segCount, icon: '🔊' },
          { label: 'Words',     value: wordCount.toLocaleString(), icon: '📝' },
        ].map(stat => (
          <div key={stat.label} className="card" style={{ padding: '12px 20px', display: 'flex', alignItems: 'center', gap: 10, flex: '1 1 140px' }}>
            <span style={{ fontSize: 22 }}>{stat.icon}</span>
            <div>
              <p style={{ fontSize: 11, color: 'var(--clr-text-muted)', marginBottom: 2, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{stat.label}</p>
              <p style={{ fontSize: 18, fontWeight: 700, color: 'var(--clr-text)' }}>{stat.value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Phase 2 CTA (disabled) */}
      <div className="card" style={{ marginBottom: 28, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
        <div>
          <p style={{ fontWeight: 700, marginBottom: 4 }}>Ready for NLP Analysis</p>
          <p style={{ fontSize: 13, color: 'var(--clr-text-muted)' }}>
            Phase 2 will run NER, topic modeling, and sentence classification on this transcript.
          </p>
        </div>
        <button
          id="analyze-btn"
          disabled
          title="Coming in Phase 2"
          style={{
            padding: '10px 24px', borderRadius: 'var(--radius-sm)',
            background: 'var(--grad-brand)', color: '#fff', fontWeight: 700, fontSize: 14,
            border: 'none', cursor: 'not-allowed', opacity: 0.5,
            whiteSpace: 'nowrap',
          }}
        >
          Analyze Meeting →
        </button>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 2, marginBottom: 16, background: 'var(--clr-surface)', borderRadius: 'var(--radius-sm)', padding: 4, width: 'fit-content' }}>
        {['segments', 'fulltext'].map(tab => (
          <button
            key={tab}
            id={`tab-${tab}`}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: '7px 18px',
              borderRadius: 'var(--radius-sm)',
              border: 'none',
              background: activeTab === tab ? 'var(--clr-surface-2)' : 'transparent',
              color: activeTab === tab ? 'var(--clr-text)' : 'var(--clr-text-muted)',
              fontWeight: activeTab === tab ? 600 : 400,
              fontSize: 13, cursor: 'pointer',
              transition: 'all var(--transition)',
            }}
          >
            {tab === 'segments' ? '🔊 Segments' : '📄 Full Text'}
          </button>
        ))}
      </div>

      {/* Segments tab */}
      {activeTab === 'segments' && (
        <div className="card" style={{ padding: '8px 0', maxHeight: 520, overflowY: 'auto' }}>
          {segments.length === 0 ? (
            <p style={{ padding: '24px', color: 'var(--clr-text-muted)', textAlign: 'center' }}>
              No segments found.
            </p>
          ) : segments.map((seg, i) => (
            <div key={i} className="segment-item">
              <span className="segment-timestamp">
                [{fmtTs(seg.start)} → {fmtTs(seg.end)}]
              </span>
              <span className="segment-text">{seg.text}</span>
            </div>
          ))}
        </div>
      )}

      {/* Full text tab */}
      {activeTab === 'fulltext' && (
        <div className="card" style={{ position: 'relative' }}>
          <button
            id="copy-transcript-btn"
            onClick={handleCopy}
            style={{
              position: 'absolute', top: 16, right: 16,
              padding: '6px 14px', borderRadius: 'var(--radius-sm)',
              background: copied ? 'rgba(16,185,129,0.15)' : 'rgba(99,102,241,0.15)',
              border: `1px solid ${copied ? 'var(--clr-success)' : 'var(--clr-border)'}`,
              color: copied ? 'var(--clr-success)' : 'var(--clr-text-muted)',
              fontSize: 12, fontWeight: 600, cursor: 'pointer',
              transition: 'all var(--transition)',
            }}
          >
            {copied ? '✓ Copied' : '⎘ Copy'}
          </button>
          <p style={{
            fontSize: 14, lineHeight: 1.8, color: 'var(--clr-text-muted)',
            whiteSpace: 'pre-wrap', wordBreak: 'break-word',
            maxHeight: 500, overflowY: 'auto',
            paddingRight: 8,
          }}>
            {full_text || 'No transcript text available.'}
          </p>
        </div>
      )}

    </div>
  )
}

function btnStyle(variant) {
  const base = { padding: '10px 20px', borderRadius: 'var(--radius-sm)', fontWeight: 600, fontSize: 13, cursor: 'pointer', border: 'none' }
  if (variant === 'secondary') return { ...base, background: 'var(--clr-surface-2)', color: 'var(--clr-text)' }
  return { ...base, background: 'var(--grad-brand)', color: '#fff' }
}
