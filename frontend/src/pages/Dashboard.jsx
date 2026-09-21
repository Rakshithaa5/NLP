import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { getAnalysis, getTranscript, analyzeMeeting, exportPdf } from '../services/api'
import MeetingHeader from '../components/meeting/MeetingHeader'
import Overview from '../components/meeting/Overview'
import TranscriptViewer from '../components/meeting/TranscriptViewer'
import Analytics from '../components/meeting/Analytics'
import { normalizeAnalysis, normalizeMeeting } from '../components/meeting/data'
import '../components/meeting/meeting.css'

export default function Dashboard() {
  const {fileId} = useParams()
  return <MeetingDashboard key={fileId} fileId={fileId}/>
}
function MeetingDashboard({fileId}) {
  const [params, setParams] = useSearchParams()
  const requested = params.get('tab')
  const tab = ['overview', 'transcript', 'analytics'].includes(requested) ? requested : 'overview'
  const [analysis, setAnalysis] = useState(null), [meeting, setMeeting] = useState(normalizeMeeting(null))
  const [loading, setLoading] = useState(true), [busy, setBusy] = useState(false), [exporting, setExporting] = useState(false)
  const [error, setError] = useState(''), [transcriptError, setTranscriptError] = useState(''), [reload, setReload] = useState(0)
  const [target, setTarget] = useState(null)
  useEffect(() => {
    let current = true
    Promise.allSettled([getAnalysis(fileId), getTranscript(fileId)]).then(([a, m]) => {
      if (!current) return
      if (a.status === 'fulfilled') setAnalysis(normalizeAnalysis(a.value))
      else if (a.reason?.status !== 404) setError(a.reason?.message || 'Analysis could not be loaded.')
      if (m.status === 'fulfilled') setMeeting(normalizeMeeting(m.value))
      else setTranscriptError(m.reason?.message || 'Transcript could not be loaded.')
      setLoading(false)
    })
    return () => {current = false}
  }, [fileId, reload])
  function retry() {setLoading(true); setError(''); setTranscriptError(''); setReload(v => v + 1)}
  async function runAnalysis() {
    setBusy(true); setError('')
    try {setAnalysis(normalizeAnalysis(await analyzeMeeting(fileId)))}
    catch (e) {setError(e.message || 'Analysis failed. Please retry.')}
    finally {setBusy(false)}
  }
  async function download() {
    setExporting(true); setError('')
    try {await exportPdf(fileId)} catch (e) {setError(e.message || 'PDF export failed.')}
    finally {setExporting(false)}
  }
  const activate = value => setParams(value === 'overview' ? {} : {tab: value})
  function jump(id) {setTarget({id, nonce: Date.now()}); activate('transcript')}
  const data = analysis || normalizeAnalysis(null)
  return <div className="mi-dashboard"><Link className="mi-back" to="/history">&#8592; Meeting history</Link>
    <MeetingHeader meeting={meeting} busy={busy} exporting={exporting} hasAnalysis={!!analysis} onAnalyze={runAnalysis} onExport={download}/>
    {error && <div role="alert" className="mi-notice mi-error">{error} <button onClick={retry}>Retry loading</button> <button disabled={busy} onClick={runAnalysis}>Retry analysis</button></div>}
    {transcriptError && <div role="alert" className="mi-notice">Transcript unavailable: {transcriptError} <button onClick={retry}>Retry</button></div>}
    {busy && <div role="status" className="mi-notice">Analysing the transcript. Your existing report remains available while this runs.</div>}
    {loading ? <div role="status" className="mi-loading"><span className="mi-eyebrow">Preparing your meeting</span><div/><div/><div/></div> : <>
      {analysis && (data.intelligence.version !== 2 || data.analysis_state === 'legacy') && <div className="mi-notice">This meeting uses an older report format. Re-analyse it to generate validated insights and transcript evidence.</div>}
      {data.analysis_attempt?.state === 'failed' && <div role="alert" className="mi-notice mi-error">The latest analysis failed. The previous report is shown below. <button disabled={busy} onClick={runAnalysis}>Retry analysis</button></div>}
      {data.analysis_state === 'partial' && <div role="status" className="mi-notice">Some sections could not be generated. Available results are shown below. <button disabled={busy} onClick={runAnalysis}>Retry analysis</button></div>}
      {data.intelligence.limitations.map((message, index) => <div className="mi-notice" key={index}>{message}</div>)}
      <div className="mi-tabs" role="tablist" aria-label="Meeting views">{['overview', 'transcript', 'analytics'].map((value, index, tabs) => <button role="tab" id={`tab-${value}`} aria-controls={`panel-${value}`} aria-selected={tab === value} tabIndex={tab === value ? 0 : -1} key={value} onClick={() => activate(value)} onKeyDown={e => {
        let next
        if (e.key === 'ArrowRight') next = tabs[(index + 1) % tabs.length]
        if (e.key === 'ArrowLeft') next = tabs[(index + tabs.length - 1) % tabs.length]
        if (e.key === 'Home') next = tabs[0]
        if (e.key === 'End') next = tabs[tabs.length - 1]
        if (next) {e.preventDefault(); activate(next); document.getElementById(`tab-${next}`)?.focus()}
      }}>{value[0].toUpperCase() + value.slice(1)}</button>)}</div>
      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === 'overview' && (!analysis ? <section className="mi-panel mi-welcome"><span className="mi-eyebrow">Transcript ready</span><h2>Turn this meeting into a clear next step.</h2><p>Generate source-backed highlights, actions, decisions, and discussion topics.</p><button className="mi-primary" disabled={busy} onClick={runAnalysis}>{busy ? 'Analysing...' : 'Analyse meeting'}</button></section> : <Overview analysis={data} segments={meeting.segments} onJump={jump}/>)}
        {tab === 'transcript' && <TranscriptViewer key={target?.nonce || 'initial'} meeting={meeting} intelligence={data.intelligence} target={target}/>}
        {tab === 'analytics' && <Analytics analysis={data} meeting={meeting}/>}
      </div>
    </>}
  </div>
}
