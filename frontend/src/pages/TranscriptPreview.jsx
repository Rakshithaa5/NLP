/**
 * pages/TranscriptPreview.jsx -- Evernote-inspired transcript preview.
 * Logic preserved exactly; visual treatment upgraded.
 */
import { useEffect, useState } from 'react'
import { useParams, useLocation, useNavigate } from 'react-router-dom'
import { getTranscript } from '../services/api'

function fmtDuration(secs) {
  if (!secs) return '--'
  const h = Math.floor(secs / 3600), m = Math.floor((secs % 3600) / 60), s = Math.floor(secs % 60)
  if (h > 0) return `${h}h ${String(m).padStart(2,'0')}m ${String(s).padStart(2,'0')}s`
  return `${m}m ${String(s).padStart(2,'0')}s`
}
function fmtTs(secs) {
  const m = Math.floor(secs / 60), s = Math.floor(secs % 60)
  return `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`
}

export default function TranscriptPreview() {
  const { fileId } = useParams()
  const location   = useLocation()
  const navigate   = useNavigate()

  const [data, setData]       = useState(location.state?.transcript ?? null)
  const [loading, setLoading] = useState(!data)
  const [error, setError]     = useState(null)
  const [copied, setCopied]   = useState(false)
  const [activeTab, setActiveTab] = useState('segments')

  useEffect(() => {
    if (data) return
    setLoading(true)
    getTranscript(fileId)
      .then(setData)
      .catch(e => setError(e.message ?? 'Failed to load transcript.'))
      .finally(() => setLoading(false))
  }, [fileId, data])

  const handleCopy = () => {
    if (!data?.full_text) return
    navigator.clipboard.writeText(data.full_text).then(() => {
      setCopied(true); setTimeout(() => setCopied(false), 2000)
    })
  }

  if (loading) return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', gap: 14 }}>
      <svg className="animate-spin" width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="var(--clr-primary)" strokeWidth="2.5" strokeLinecap="round">
        <circle cx="12" cy="12" r="10" strokeOpacity="0.15"/>
        <path d="M12 2a10 10 0 0 1 10 10"/>
      </svg>
      <p style={{ color: 'var(--clr-text-muted)', fontSize: 14 }}>Loading transcript…</p>
    </div>
  )

  if (error) return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', gap: 14, padding: 24 }}>
      <div style={{ width: 56, height: 56, borderRadius: '50%', background: '#fff5f5', border: '1px solid #fecaca', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--clr-error)" strokeWidth="2.5" strokeLinecap="round">
          <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
      </div>
      <p style={{ color: 'var(--clr-error)', fontWeight: 600 }}>{error}</p>
      <button id="transcript-back-btn" onClick={() => navigate('/')} style={{ padding: '9px 18px', borderRadius: 'var(--radius-sm)', background: 'var(--clr-surface)', border: '1px solid var(--clr-border-2)', color: 'var(--clr-text-2)', fontWeight: 600, fontSize: 13, cursor: 'pointer' }}>
        Back to Upload
      </button>
    </div>
  )

  const { filename, duration, language, segments = [], full_text = '' } = data ?? {}
  const wordCount = full_text.trim().split(/\s+/).filter(Boolean).length
  const segCount  = segments.length

  return (
    <div className="page-container-sm animate-fade-up">

      <button id="transcript-back-btn" onClick={() => navigate('/')}
        style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: 'none', border: 'none', color: 'var(--clr-text-muted)', fontSize: 13, cursor: 'pointer', marginBottom: 28, padding: 0, fontWeight: 500 }}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><polyline points="15 18 9 12 15 6"/></svg>
        Back to Upload
      </button>

      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <p style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--clr-primary-h)', marginBottom: 6 }}>
          Transcript Ready
        </p>
        <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 6, letterSpacing: '-0.03em' }}>{filename || 'Recording'}</h1>
        <p style={{ color: 'var(--clr-text-muted)', fontSize: 13 }}>Review the transcript below, then run NLP analysis.</p>
      </div>

      {/* Stat pills */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 24 }}>
        {[
          { label: 'Duration', value: fmtDuration(duration), icon: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> },
          { label: 'Language', value: (language ?? '--').toUpperCase(), icon: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg> },
          { label: 'Segments', value: segCount, icon: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/></svg> },
          { label: 'Words',    value: wordCount.toLocaleString(), icon: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg> },
        ].map(stat => (
          <div key={stat.label} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 16px', background: 'var(--clr-surface)', border: '1px solid var(--clr-border)', borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-xs)', flex: '1 1 120px' }}>
            <span style={{ color: 'var(--clr-primary)' }}>{stat.icon}</span>
            <div>
              <p style={{ fontSize: 10, color: 'var(--clr-text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 1 }}>{stat.label}</p>
              <p style={{ fontSize: 17, fontWeight: 700, color: 'var(--clr-text)' }}>{stat.value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Analyze CTA */}
      <div style={{ background: 'var(--clr-surface)', border: '1px solid var(--clr-border)', borderRadius: 'var(--radius-lg)', padding: '20px 24px', marginBottom: 28, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap', boxShadow: 'var(--shadow-sm)' }}>
        <div>
          <p style={{ fontWeight: 700, marginBottom: 4, color: 'var(--clr-text)' }}>Ready for NLP Analysis</p>
          <p style={{ fontSize: 13, color: 'var(--clr-text-muted)' }}>
            Run the full pipeline — NER, topic modeling, action items, decisions, and AI summarization.
          </p>
        </div>
        <button
          id="analyze-btn"
          onClick={() => navigate(`/dashboard/${fileId}`)}
          style={{ padding: '10px 22px', borderRadius: 'var(--radius-sm)', background: 'var(--clr-primary)', color: '#fff', fontWeight: 700, fontSize: 14, border: 'none', cursor: 'pointer', whiteSpace: 'nowrap', transition: 'background var(--transition)' }}
          onMouseEnter={e => e.currentTarget.style.background = 'var(--clr-primary-h)'}
          onMouseLeave={e => e.currentTarget.style.background = 'var(--clr-primary)'}
        >
          Analyze Meeting →
        </button>
      </div>

      {/* Tabs */}
      <div className="mi-tabs" style={{ marginBottom: 16 }}>
        {['segments', 'fulltext'].map(tab => (
          <button key={tab} id={`tab-${tab}`} role="tab" aria-selected={activeTab === tab} onClick={() => setActiveTab(tab)}>
            {tab === 'segments' ? 'Segments' : 'Full Text'}
          </button>
        ))}
      </div>

      {/* Segments */}
      {activeTab === 'segments' && (
        <div style={{ border: '1px solid var(--clr-border)', borderRadius: 'var(--radius-lg)', background: 'var(--clr-surface)', overflow: 'hidden', maxHeight: 520, overflowY: 'auto' }}>
          {segments.length === 0 ? (
            <p style={{ padding: 24, color: 'var(--clr-text-muted)', textAlign: 'center', fontSize: 14 }}>No segments found.</p>
          ) : segments.map((seg, i) => (
            <div key={i} className="segment-item">
              <span className="segment-timestamp">[{fmtTs(seg.start)} - {fmtTs(seg.end)}]</span>
              <span className="segment-text">{seg.text}</span>
            </div>
          ))}
        </div>
      )}

      {/* Full text */}
      {activeTab === 'fulltext' && (
        <div style={{ border: '1px solid var(--clr-border)', borderRadius: 'var(--radius-lg)', background: 'var(--clr-surface)', padding: 24, position: 'relative' }}>
          <button id="copy-transcript-btn" onClick={handleCopy}
            style={{ position: 'absolute', top: 16, right: 16, padding: '6px 14px', borderRadius: 'var(--radius-sm)', background: copied ? 'var(--clr-primary-bg)' : 'var(--clr-surface-2)', border: `1px solid ${copied ? 'var(--clr-primary-l)' : 'var(--clr-border)'}`, color: copied ? 'var(--clr-primary-h)' : 'var(--clr-text-muted)', fontSize: 12, fontWeight: 600, cursor: 'pointer', transition: 'all var(--transition)' }}>
            {copied ? '✓ Copied' : 'Copy'}
          </button>
          <p style={{ fontSize: 14, lineHeight: 1.8, color: 'var(--clr-text-2)', whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: 500, overflowY: 'auto', paddingRight: 8 }}>
            {full_text || 'No transcript text available.'}
          </p>
        </div>
      )}
    </div>
  )
}
