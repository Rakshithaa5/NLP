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
import { getAnalysis, getTranscript, analyzeMeeting, exportPdf } from '../services/api'
import { TranslationProvider, MeetingLanguageControl, TranslationStatus } from '../components/meeting/TranslationContext'
import { useEnglishDisplay } from '../components/meeting/translationHooks'
import NavBar from '../components/NavBar'
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
export default function Dashboard() {
  const { fileId } = useParams()
  return <TranslationProvider key={fileId} fileId={fileId}><MeetingDashboard fileId={fileId} /></TranslationProvider>
}

function MeetingDashboard({ fileId }) {
  const [params, setParams] = useSearchParams()
  const requested = params.get('tab')
  const tab = ['overview','transcript','analytics','topics'].includes(requested) ? requested : 'overview'

  const [analysis, setAnalysis]   = useState(null)
  const [meeting, setMeeting]     = useState(normalizeMeeting(null))
  const [loading, setLoading]     = useState(true)
  const [busy, setBusy]           = useState(false)
  const [exporting, setExporting] = useState(false)
  const [error, setError]         = useState('')
  const [transcriptError, setTranscriptError] = useState('')
  const [reload, setReload]       = useState(0)
  const [retryAt, setRetryAt]     = useState(0)
  const [now, setNow]             = useState(() => Date.now())
  const [errorSource, setErrorSource] = useState('loading')
  const [activeSegmentId, setActiveSegmentId]             = useState(null)
  const [selectedEvidenceSegmentIds, setSelectedEvidenceSegmentIds] = useState([])
  const [seekRequest, setSeekRequest] = useState(null)

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
  function jump(value) {
    if (typeof value === 'object' && value !== null) {
      const resolved = resolveEvidenceTarget(value, meeting.segments)
      if (!resolved) { setTarget({ id: null, nonce: Date.now() }); setSelectedEvidenceSegmentIds([]); return }
      setTarget({ id: resolved.segmentId, nonce: Date.now() })
      setSelectedEvidenceSegmentIds(Array.isArray(resolved.segmentIds) ? resolved.segmentIds : [resolved.segmentId])
      requestSeek(resolved.seconds, true); activate('transcript'); return
    }
    setTarget({ id: value, nonce: Date.now() }); setSelectedEvidenceSegmentIds([])
    const segment = meeting.segments.find(item => item.id === value)
    if (segment && Number.isFinite(segment.start)) requestSeek(segment.start, true)
    activate('transcript')
  }

  // Translate one immutable display copy; mutations and evidence navigation use originals.
  const sourceDisplay = useMemo(() => ({
    meeting: meeting.segments.length ? {...meeting, full_text: ''} : meeting,
    analysis,
  }), [meeting, analysis])
  const translated = useEnglishDisplay(sourceDisplay)
  const displayMeeting = useMemo(() => translated === sourceDisplay ? meeting : ({...translated.meeting,
    full_text: translated.meeting.segments.length
      ? translated.meeting.segments.map(segment => segment.text).join(' ')
      : translated.meeting.full_text,
  }), [translated, sourceDisplay, meeting])
  const data = translated.analysis || normalizeAnalysis(null)
  const displaySegments = displayMeeting.segments


  return (
    <div className="dash-shell">
      <NavBar tab={tab} activate={activate} />

      <main id="main-content" tabIndex={-1} className="dash-content">
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
          {!loading && <MeetingLanguageControl language={meeting.language} />}
        </div>

        <div className="dash-inner mi-dashboard">
          <TranslationStatus />
          <MeetingHeader
            meeting={meeting} busy={busy} analyzeDisabled={analysisDisabled}
            exporting={exporting} hasAnalysis={!!analysis}
            onAnalyze={runAnalysis} onExport={download}
          />



          {!loading && fileId && <AskThisMeeting fileId={fileId} meeting={displayMeeting} onJump={jump} />}

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

          {!loading && <>
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

          </>}
          <div className={`report-layout${!loading && analysis && tab === 'overview' ? ' report-overview' : ''}`}>
          {fileId && <MeetingPlayer fileId={fileId} meeting={meeting} onActiveSegmentChange={setActiveSegmentId} seekRequest={seekRequest} onSeekHandled={() => setSeekRequest(null)} />}
          {loading ? (
            <div role="status" className="mi-loading">
              <span className="mi-eyebrow">Preparing your meeting</span>
              <div /><div /><div />
            </div>
          ) : (
            <>
              <div className="mi-tabs" role="tablist" aria-label="Meeting views">
                {['overview','transcript','analytics','topics'].map((value, index, tabs) => (
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
                    <Overview analysis={data} segments={displaySegments} onJump={jump} fileId={fileId} sourceItems={analysis.intelligence.action_items} />
                  )
                )}
                {tab === 'transcript' && (
                  <TranscriptViewer
                    key={target?.nonce || 'initial'}
                    meeting={displayMeeting} intelligence={data.intelligence} target={target}
                    activeSegmentId={activeSegmentId}
                    selectedEvidenceSegmentIds={selectedEvidenceSegmentIds}
                    onSeek={requestSeek} onSegmentSelect={jump}
                  />
                )}
                {tab === 'analytics' && <Analytics analysis={data} meeting={meeting} />}
                {tab === 'topics' && <TopicExplorer fileId={fileId} onJump={jump} />}
              </div>
            </>
          )}
          </div>
        </div>
      </main>
    </div>
  )
}
