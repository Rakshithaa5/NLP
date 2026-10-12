/**
 * pages/Home.jsx -- Evernote-inspired landing/upload page.
 *
 * Premium light-mode upload experience:
 * - Hero with compelling headline
 * - Large drag-and-drop upload zone (UploadCard)
 * - Recent meetings sidebar panel (live data from API)
 * - Feature cards below
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import UploadCard from '../components/UploadCard'
import { listMeetings } from '../services/api'

function fmtDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diff = Math.floor((now - d) / 1000)
  if (diff < 60) return 'Just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  if (diff < 172800) return 'Yesterday'
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}

function fmtDur(s) {
  if (!s) return null
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  if (m >= 60) return `${Math.floor(m/60)}h ${m%60}m`
  return `${m}m ${String(sec).padStart(2,'0')}s`
}

const STATUS = {
  done:       { label: 'Analyzed', cls: 'pill-green' },
  processing: { label: 'Processing', cls: 'pill-blue' },
  uploaded:   { label: 'Uploaded', cls: 'pill-amber' },
  error:      { label: 'Error', cls: 'pill-red' },
}

export default function Home() {
  const navigate = useNavigate()
  const [recent, setRecent] = useState([])

  useEffect(() => {
    listMeetings()
      .then(res => setRecent((res.meetings || []).slice(0, 5)))
      .catch(() => {})
  }, [])

  const handleSuccess = (data) => {
    navigate(`/transcript/${data.file_id}`, { state: { transcript: data } })
  }

  const handleError = (msg) => {
    console.error('[Home] Upload error:', msg)
  }

  return (
    <div>
      <main className="page-container" style={{ maxWidth: 1080 }}>

        {/* ── Hero ────────────────────────────────────────────────────── */}
        <div style={{ textAlign: 'center', marginBottom: 52 }} className="animate-fade-up">
          <div className="hero-badge">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
            </svg>
            AI-Powered Meeting Analysis
          </div>

          <h1 style={{
            fontSize: 'clamp(32px,5vw,56px)',
            fontWeight: 800,
            lineHeight: 1.1,
            letterSpacing: '-0.03em',
            marginBottom: 20,
            color: 'var(--clr-text)',
          }}>
            Turn every meeting into{' '}
            <span className="gradient-text">meaningful insights</span>
          </h1>

          <p style={{
            fontSize: 18,
            color: 'var(--clr-text-muted)',
            maxWidth: 520,
            margin: '0 auto 40px',
            lineHeight: 1.7,
            fontWeight: 400,
          }}>
            Upload any recording. Our NLP pipeline extracts transcripts,
            action items, decisions, and summaries — automatically.
          </p>

          {/* Pipeline steps */}
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 4, flexWrap: 'wrap', marginBottom: 0 }}>
            {[
              { step: 'Upload', icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg> },
              { step: 'Transcribe', icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><circle cx="12" cy="12" r="10"/><polyline points="10 15 10 12 14 12 14 15"/><line x1="7" y1="8" x2="17" y2="8"/></svg> },
              { step: 'Analyze', icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg> },
              { step: 'Insights', icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg> },
            ].map((item, i, arr) => (
              <div key={item.step} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{
                  display: 'inline-flex', alignItems: 'center', gap: 5,
                  padding: '5px 12px', borderRadius: 99,
                  background: i === 0 ? 'var(--clr-primary-bg)' : 'var(--clr-surface)',
                  border: '1px solid ' + (i === 0 ? 'var(--clr-primary-l)' : 'var(--clr-border)'),
                  fontSize: 12, fontWeight: 600,
                  color: i === 0 ? 'var(--clr-primary-h)' : 'var(--clr-text-muted)',
                }}>
                  {item.icon}{item.step}
                </span>
                {i < arr.length - 1 && (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--clr-text-dim)" strokeWidth="2.5" strokeLinecap="round"><polyline points="9 18 15 12 9 6"/></svg>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* ── Upload + Recent meetings layout ─────────────────────────── */}
        <div style={{ display: 'grid', gridTemplateColumns: recent.length ? '1fr 320px' : '1fr', gap: 24, marginBottom: 56, alignItems: 'start' }}>

          {/* Upload area */}
          <div className="animate-fade-up delay-100">
            <UploadCard onSuccess={handleSuccess} onError={handleError} />
          </div>

          {/* Recent meetings panel */}
          {recent.length > 0 && (
            <aside className="card-sm animate-fade-up delay-200" style={{ padding: 20 }}>
              <p style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--clr-text-dim)', marginBottom: 14 }}>
                Recent Meetings
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {recent.map(m => {
                  const st = STATUS[m.status] || STATUS.uploaded
                  const ext = m.filename?.split('.').pop()?.toUpperCase() || 'FILE'
                  return (
                    <button
                      key={m.id}
                      id={`recent-meeting-${m.id}`}
                      onClick={() => navigate(m.status === 'done' ? `/dashboard/${m.id}` : `/transcript/${m.id}`)}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 10,
                        padding: '10px 10px', borderRadius: 'var(--radius-sm)',
                        border: 'none', background: 'transparent',
                        cursor: 'pointer', textAlign: 'left', width: '100%',
                        transition: 'background var(--transition)',
                      }}
                      onMouseEnter={e => e.currentTarget.style.background = 'var(--clr-surface-2)'}
                      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                    >
                      <div style={{
                        width: 34, height: 34, borderRadius: 8,
                        background: 'var(--clr-surface-2)', border: '1px solid var(--clr-border)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 9, fontWeight: 800, color: 'var(--clr-text-dim)',
                        letterSpacing: '0.04em', flexShrink: 0,
                      }}>{ext}</div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--clr-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', margin: 0 }}>
                          {m.filename || 'Untitled'}
                        </p>
                        <p style={{ fontSize: 11, color: 'var(--clr-text-dim)', margin: '2px 0 0' }}>
                          {fmtDate(m.uploaded_at)}{fmtDur(m.duration) ? ` · ${fmtDur(m.duration)}` : ''}
                        </p>
                      </div>
                      <span className={`pill ${st.cls}`} style={{ flexShrink: 0, fontSize: 10 }}>{st.label}</span>
                    </button>
                  )
                })}
              </div>
              <div style={{ borderTop: '1px solid var(--clr-border)', marginTop: 12, paddingTop: 12 }}>
                <button
                  id="view-all-meetings-btn"
                  onClick={() => navigate('/history')}
                  style={{ background: 'none', border: 'none', color: 'var(--clr-primary-h)', fontSize: 13, fontWeight: 600, cursor: 'pointer', padding: 0, width: '100%', textAlign: 'center' }}
                >
                  View all meetings →
                </button>
              </div>
            </aside>
          )}
        </div>

        {/* ── Feature cards ────────────────────────────────────────────── */}
        <div className="animate-fade-up delay-300">
          <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--clr-text-dim)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 16, textAlign: 'center' }}>
            Powered by
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: 14 }}>
            {[
              { icon: '🎙', title: 'Faster-Whisper STT', desc: 'CTranslate2-optimised speech recognition — fast even on CPU.' },
              { icon: '🧠', title: 'spaCy NER', desc: 'Named entity recognition for people, orgs, dates, and locations.' },
              { icon: '📋', title: 'Action Item Extraction', desc: 'Dependency parsing pulls person + task + deadline automatically.' },
              { icon: '📄', title: 'BART Summarization', desc: 'Extractive + abstractive summaries powered by Hugging Face.' },
            ].map(feat => (
              <div key={feat.title} style={{
                background: 'var(--clr-surface)', border: '1px solid var(--clr-border)',
                borderRadius: 'var(--radius-md)', padding: '18px 20px',
                boxShadow: 'var(--shadow-xs)',
              }}>
                <span style={{ fontSize: 24, display: 'block', marginBottom: 10 }}>{feat.icon}</span>
                <p style={{ fontWeight: 700, marginBottom: 5, fontSize: 14, color: 'var(--clr-text)' }}>{feat.title}</p>
                <p style={{ fontSize: 13, color: 'var(--clr-text-muted)', lineHeight: 1.6 }}>{feat.desc}</p>
              </div>
            ))}
          </div>
        </div>

      </main>
    </div>
  )
}
