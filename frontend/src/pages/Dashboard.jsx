/**
 * pages/Dashboard.jsx -- Evernote-inspired meeting analysis workspace.
 *
 * Full functionality preserved:
 * - Analysis fetching, retry, rate-limit handling
 * - Tab navigation: overview / transcript / analytics
 * - MeetingPlayer, AskThisMeeting, Overview, TranscriptViewer, Analytics
 *
 * Visual: sidebar + dash-content layout with dash-topbar.
 */
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { getAnalysis, getTranscript, analyzeMeeting, exportPdf, getDiarization } from '../services/api'
import SpeakerPanel from '../components/meeting/SpeakerPanel'
import MeetingHeader from '../components/meeting/MeetingHeader'
import Overview from '../components/meeting/Overview'
import TranscriptViewer from '../components/meeting/TranscriptViewer'
import Analytics from '../components/meeting/Analytics'
import MeetingPlayer from '../components/meeting/MeetingPlayer'
import AskThisMeeting from '../components/meeting/AskThisMeeting'
import TopicExplorer from '../components/meeting/TopicExplorer'
import { normalizeAnalysis, normalizeMeeting } from '../components/meeting/data'
import { resolveEvidenceTarget } from '../components/meeting/playback'
import '../components/meeting/meeting.css'
import '../components/meeting/playback.css'
import '../components/meeting/chatbot.css'

/* ── Sidebar for meeting workspace ───────────────────────────────────────── */
function MeetingSidebar({ fileId, tab, activate }) {
  const navItems = [
    { id: 'overview',   label: 'Overview',   icon: <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg> },
    { id: 'transcript', label: 'Transcript',  icon: <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg> },
    { id: 'analytics',  label: 'Analytics',  icon: <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6"  y1="20" x2="6"  y2="14"/></svg> },
    { id: 'topics',     label: 'Topics',     icon: <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.22 4.22l2.12 2.12M17.66 17.66l2.12 2.12M2 12h3M19 12h3M4.22 19.78l2.12-2.12M17.66 6.34l2.12-2.12"/></svg> },
    { id: 'speakers',   label: 'Speakers',   icon: <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg> },
  ]
  return (
    <aside className="sidebar">
      <Link to="/" className="sidebar-header" style={{ textDecoration: 'none' }}>
        <div className="sidebar-logo" aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
          </svg>
        </div>
        <span className="sidebar-name">Meeting Intel</span>
      </Link>

      <div className="sidebar-section">
        <span className="sidebar-section-label">Navigation</span>
        <Link to="/" className="sidebar-item" id="sidebar-upload">
          <svg className="sidebar-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
          New Meeting
        </Link>
        <Link to="/history" className="sidebar-item" id="sidebar-history">
          <svg className="sidebar-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
          </svg>
          All Meetings
        </Link>

        {fileId && (
          <>
            <span className="sidebar-section-label" style={{ marginTop: 16 }}>This Meeting</span>
            {navItems.map(item => (
              <button
                key={item.id}
                id={`sidebar-${item.id}`}
                className={`sidebar-item${tab === item.id ? ' active' : ''}`}
                onClick={() => activate(item.id)}
              >
                <span className="sidebar-icon">{item.icon}</span>
                {item.label}
              </button>
            ))}
          </>
        )}
      </div>

      <div className="sidebar-footer">
        <p style={{ fontSize: 11, color: 'var(--clr-text-dim)', lineHeight: 1.5 }}>
          Meeting Intelligence System
        </p>
      </div>
    </aside>
  )
}

export default function Dashboard() {
  const { fileId } = useParams()
  return <MeetingDashboard key={fileId} fileId={fileId} />
}

function MeetingDashboard({ fileId }) {
  const [params, setParams] = useSearchParams()
  const requested = params.get('tab')
  const tab = ['overview','transcript','analytics','topics','speakers'].includes(requested) ? requested : 'overview'

  const [analysis, setAnalysis]   = useState(null)
  const [meeting, setMeeting]     = useState(normalizeMeeting(null))
  const [loading, setLoading]     = useState(true)
  const [busy, setBusy]           = useState(false)
  const [exporting, setExporting] = useState(false)
  const [error, setError]         = useState('')
  const [transcriptError, setTranscriptError] = useState('')
  const [reload, setReload]       = useState(0)
  const [retryAt, setRetryAt]     = useState(0)
  const [now, setNow]             = useState(Date.now())
  const [errorSource, setErrorSource] = useState('loading')
  const [activeSegmentId, setActiveSegmentId]             = useState(null)
  const [selectedEvidenceSegmentIds, setSelectedEvidenceSegmentIds] = useState([])
  const [seekRequest, setSeekRequest] = useState(null)
  const [diarization, setDiarization] = useState(null)
  const [showSpeakerLabels, setShowSpeakerLabels] = useState(true)

  const retrySeconds    = Math.max(0, Math.ceil((retryAt - now) / 1000))
  const analysisDisabled = busy || retrySeconds > 0

  useEffect(() => {
    if (!retryAt) return
    const timer = setInterval(() => { const c = Date.now(); setNow(c); if (c >= retryAt) clearInterval(timer) }, 1000)
    return () => clearInterval(timer)
  }, [retryAt])

  function handleError(e, source) {
    setError(e.message || 'Request failed. Please retry.')
    setErrorSource(source)
    if (e.status === 429) { setNow(Date.now()); setRetryAt(Date.now() + (e.retryAfter ?? 60) * 1000) }
  }

  const [target, setTarget] = useState(null)

  useEffect(() => {
    let current = true
    Promise.allSettled([getAnalysis(fileId), getTranscript(fileId)]).then(([a, m]) => {
      if (!current) return
      if (a.status === 'fulfilled') {
        setAnalysis(normalizeAnalysis(a.value))
        if (a.value.analysis_attempt?.state === 'rate_limited') {
          setError(a.value.analysis_attempt.message || 'Groq rate limit reached.')
          setErrorSource('analysis')
          setNow(Date.now())
          setRetryAt((a.value.analysis_attempt.retry_at || 0) * 1000)
        }
      } else if (a.reason?.status !== 404) {
        handleError(a.reason, a.reason?.status === 429 ? 'analysis' : 'loading')
      }
      if (m.status === 'fulfilled') setMeeting(normalizeMeeting(m.value))
      else setTranscriptError(m.reason?.message || 'Transcript could not be loaded.')
      getDiarization(fileId).then(d => { if (d?.state === 'complete') setDiarization(d) }).catch(() => {})
      setLoading(false)
    })
    return () => { current = false }
  }, [fileId, reload])

  function retry() { setLoading(true); setError(''); setTranscriptError(''); setReload(v => v + 1) }

  async function runAnalysis() {
    if (analysisDisabled) return
    setBusy(true); setError(''); setErrorSource('analysis')
    try { setAnalysis(normalizeAnalysis(await analyzeMeeting(fileId, undefined, true))); setRetryAt(0) }
    catch (e) { handleError(e, 'analysis') }
    finally { setBusy(false) }
  }

  async function download() {
    setExporting(true); setError('')
    try { await exportPdf(fileId) }
    catch (e) { handleError(e, 'export') }
    finally { setExporting(false) }
  }

  const activate = value => setParams(value === 'overview' ? {} : { tab: value })

  function requestSeek(seconds, shouldPlay = true) {
    if (!Number.isFinite(seconds)) return
    setSeekRequest({ seconds: Number(seconds), play: shouldPlay, nonce: Date.now() })
  }
  function scrollToPlayer() {
    document.getElementById('meeting-player')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  function jump(value) {
    if (typeof value === 'object' && value !== null) {
      const resolved = resolveEvidenceTarget(value, meeting.segments)
      if (!resolved) { setTarget({ id: null, nonce: Date.now() }); setSelectedEvidenceSegmentIds([]); return }
      setTarget({ id: resolved.segmentId, nonce: Date.now() })
      setSelectedEvidenceSegmentIds(Array.isArray(resolved.segmentIds) ? resolved.segmentIds : [resolved.segmentId])
      requestSeek(resolved.seconds, true); scrollToPlayer(); return
    }
    setTarget({ id: value, nonce: Date.now() }); setSelectedEvidenceSegmentIds([])
    const segment = meeting.segments.find(item => item.id === value)
    if (segment && Number.isFinite(segment.start)) requestSeek(segment.start, true)
    activate('transcript')
  }

  const data = analysis || normalizeAnalysis(null)
  const displaySegments = useMemo(() => meeting.segments || [], [meeting.segments])
  const diarizationSegments = diarization?.segments ?? null

  return (
    <div className="dash-shell">
      <MeetingSidebar fileId={fileId} tab={tab} activate={activate} />

      <div className="dash-content">
        {/* Topbar */}
        <div className="dash-topbar">
          <Link to="/history" className="dash-back" id="dash-back-link">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><polyline points="15 18 9 12 15 6"/></svg>
            Meeting history
          </Link>
          <span style={{ color: 'var(--clr-border)', fontSize: 16 }}>|</span>
          <span style={{ fontSize: 13, color: 'var(--clr-text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 320 }}>
            {meeting.filename || 'Meeting Analysis'}
          </span>
        </div>

        <div className="dash-inner mi-dashboard">
          <MeetingHeader
            meeting={meeting} busy={busy} analyzeDisabled={analysisDisabled}
            exporting={exporting} hasAnalysis={!!analysis}
            onAnalyze={runAnalysis} onExport={download}
          />

          {fileId && <MeetingPlayer fileId={fileId} meeting={meeting} onActiveSegmentChange={setActiveSegmentId} seekRequest={seekRequest} onSeekHandled={() => setSeekRequest(null)} />}

          {!loading && fileId && <AskThisMeeting fileId={fileId} meeting={meeting} onJump={jump} />}

          {error && (
            <div role="alert" className="mi-notice mi-error">
              <span style={{ flex: 1 }}>{error}{retrySeconds > 0 && <span role="status"> Retry in {retrySeconds}s.</span>}</span>
              {errorSource === 'loading'   && <button onClick={retry}>Retry loading</button>}
              {errorSource === 'analysis'  && <button disabled={analysisDisabled} onClick={runAnalysis}>Retry analysis</button>}
              {errorSource === 'export'    && <button disabled={exporting} onClick={download}>Retry export</button>}
            </div>
          )}

          {transcriptError && (
            <div role="alert" className="mi-notice">
              <span style={{ flex: 1 }}>Transcript unavailable: {transcriptError}</span>
              <button onClick={retry}>Retry</button>
            </div>
          )}

          {busy && <div role="status" className="mi-notice">Analysing the transcript. Your existing report remains available while this runs.</div>}

          {loading ? (
            <div role="status" className="mi-loading">
              <span className="mi-eyebrow">Preparing your meeting</span>
              <div /><div /><div />
            </div>
          ) : (
            <>
              {analysis && (data.intelligence.version !== 2 || data.analysis_state === 'legacy') && (
                <div className="mi-notice">This meeting uses an older report format. Re-analyse it to generate validated insights.</div>
              )}
              {data.analysis_attempt?.state === 'failed' && (
                <div role="alert" className="mi-notice mi-error">
                  <span style={{ flex: 1 }}>The latest analysis failed. The previous report is shown below.</span>
                  <button disabled={analysisDisabled} onClick={runAnalysis}>Retry analysis</button>
                </div>
              )}
              {data.analysis_state === 'partial' && (
                <div role="status" className="mi-notice">
                  <span style={{ flex: 1 }}>Some sections could not be generated. Available results are shown below.</span>
                  <button disabled={analysisDisabled} onClick={runAnalysis}>Retry analysis</button>
                </div>
              )}
              {data.intelligence.limitations.map((message, index) => (
                <div className="mi-notice" key={index}>{message}</div>
              ))}

              <div className="mi-tabs" role="tablist" aria-label="Meeting views">
                {['overview','transcript','analytics','topics','speakers'].map((value, index, tabs) => (
                  <button
                    role="tab" id={`tab-${value}`}
                    aria-controls={`panel-${value}`} aria-selected={tab === value}
                    tabIndex={tab === value ? 0 : -1} key={value}
                    onClick={() => activate(value)}
                    onKeyDown={e => {
                      let next
                      if (e.key === 'ArrowRight') next = tabs[(index + 1) % tabs.length]
                      if (e.key === 'ArrowLeft')  next = tabs[(index + tabs.length - 1) % tabs.length]
                      if (e.key === 'Home') next = tabs[0]
                      if (e.key === 'End')  next = tabs[tabs.length - 1]
                      if (next) { e.preventDefault(); activate(next); document.getElementById(`tab-${next}`)?.focus() }
                    }}
                  >
                    {value[0].toUpperCase() + value.slice(1)}
                  </button>
                ))}
              </div>

              <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
                {tab === 'overview' && (
                  !analysis ? (
                    <section className="mi-panel mi-welcome">
                      <span className="mi-eyebrow">Transcript ready</span>
                      <h2>Turn this meeting into a clear next step.</h2>
                      <p>Generate source-backed highlights, actions, decisions, and discussion topics.</p>
                      <button className="mi-primary" disabled={analysisDisabled} onClick={runAnalysis}>
                        {busy ? 'Analysing...' : 'Analyse meeting'}
                      </button>
                    </section>
                  ) : (
                    <Overview analysis={data} segments={displaySegments} onJump={jump} />
                  )
                )}
                {tab === 'transcript' && (
                  <TranscriptViewer
                    key={target?.nonce || 'initial'}
                    meeting={meeting} intelligence={data.intelligence} target={target}
                    activeSegmentId={activeSegmentId}
                    selectedEvidenceSegmentIds={selectedEvidenceSegmentIds}
                    onSeek={requestSeek} onSegmentSelect={jump}
                    diarizationSegments={diarizationSegments}
                    showSpeakerLabels={showSpeakerLabels}
                  />
                )}
                {tab === 'analytics' && <Analytics analysis={data} meeting={meeting} />}
                {tab === 'topics' && <TopicExplorer fileId={fileId} onJump={jump} />}
                {tab === 'speakers' && (
                  <SpeakerPanel
                    fileId={fileId}
                    diarization={diarization}
                    onDiarizationUpdate={setDiarization}
                    showLabels={showSpeakerLabels}
                    onToggleLabels={setShowSpeakerLabels}
                  />
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
